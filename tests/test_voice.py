"""voice + subtitles stages with fake TTS/STT (offline), plus WER and cue rules."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from factory.agents.brief import BriefStage
from factory.agents.script import ScriptStage
from factory.agents.subtitles import MAX_LINE, SubtitlesStage, build_cues, split_lines
from factory.agents.voice import VoiceStage
from factory.config import Settings
from factory.media.stt import wer
from factory.pipeline import PermanentStageError, StageContext
from factory.providers.llm.fake import FakeLLM
from factory.schemas.script import Script
from factory.schemas.voice import VoiceManifest
from fakes_media import FakeSTT, FakeTTS
from helpers import good_draft, pass_review, write_brief


def ctx(tmp_path: Path, stage: str, upstream: dict | None = None) -> StageContext:
    s = Settings(content_dir=tmp_path / "content", library_dir=tmp_path / "library")
    return StageContext(episode_id=uuid.uuid4(), job_id=uuid.uuid4(), stage=stage, attempt=1,
                        settings=s, workdir=tmp_path / "content" / "ep" / stage,
                        upstream=upstream or {})


def upstream(tmp_path: Path) -> dict:
    write_brief(tmp_path / "content" / "ep" / "inputs" / "brief.yaml")
    brief = BriefStage().run(ctx(tmp_path, "brief")).output_refs
    script = ScriptStage(FakeLLM([good_draft()])).run(
        ctx(tmp_path, "script", {"brief": brief})).output_refs
    return {"brief": brief, "script": script, "script_validate": {"verdict": "pass"}}


def perfect_stt(tmp_path: Path, refs: dict) -> FakeSTT:
    script = Script.model_validate_json(
        (tmp_path / "content" / refs["script"]["path"]).read_text(encoding="utf-8"))
    return FakeSTT({ln.line_id: ln.text for ln in script.lines})


# ---------------------------------------------------------------- WER


def test_wer_normalizes_case_punctuation_and_numbers() -> None:
    assert wer("Okay, Lipa, show me the inside!", "okay lipa show me the inside") == (0, 0)
    assert wer("It has 3 parts.", "It has three parts")[1] == 0
    rate, errors = wer("Blue waves are short", "Blue waves are long")
    assert errors == 1 and rate == pytest.approx(0.25)


# ---------------------------------------------------------------- voice


def test_voice_stage_writes_lines_preview_and_manifest(tmp_path: Path) -> None:
    refs = upstream(tmp_path)
    tts = FakeTTS()
    out = VoiceStage(tts, perfect_stt(tmp_path, refs)).run(ctx(tmp_path, "voice", refs))
    refs_out = out.output_refs
    manifest = VoiceManifest.model_validate_json(
        (tmp_path / "content" / refs_out["path"]).read_text(encoding="utf-8"))
    assert refs_out["overall_wer"] == 0 and refs_out["cached_lines"] == 0
    assert len(manifest.lines) == refs_out["lines"] == 14
    first = manifest.lines[0]
    hero = ctx(tmp_path, "voice").settings
    assert (tmp_path / "content" / first.file).exists() and first.voice == hero.tts_hero_voice
    assert first.pitch == hero.tts_hero_pitch
    lipa = next(v for v in manifest.lines if v.speaker == "lipa")
    assert lipa.voice == "af_sky" and lipa.speed == 1.1
    assert first.peak_dbfs <= -0.9  # normalised with a -1 dBFS ceiling
    assert manifest.lines[1].preview_start_s == pytest.approx(
        first.duration_s + manifest.gap_s, abs=1e-3)
    assert (tmp_path / "content" / manifest.preview_file).exists()
    assert (tmp_path / "content" / refs_out["report"]).read_text(encoding="utf-8").startswith(
        "# Voice report")


def test_voice_lines_are_cached_between_runs(tmp_path: Path) -> None:
    refs = upstream(tmp_path)
    stt = perfect_stt(tmp_path, refs)
    VoiceStage(FakeTTS(), stt).run(ctx(tmp_path, "voice", refs))
    tts = FakeTTS()
    out = VoiceStage(tts, stt).run(ctx(tmp_path, "voice", refs)).output_refs
    assert out["cached_lines"] == out["lines"] and tts.calls == []


def test_voice_fails_when_stt_disagrees(tmp_path: Path) -> None:
    refs = upstream(tmp_path)
    with pytest.raises(PermanentStageError, match="overall WER"):
        VoiceStage(FakeTTS(), FakeSTT(garble=True)).run(ctx(tmp_path, "voice", refs))


def test_voice_fails_on_silent_audio(tmp_path: Path) -> None:
    refs = upstream(tmp_path)
    with pytest.raises(PermanentStageError, match="silent"):
        VoiceStage(FakeTTS(silent=True), FakeSTT()).run(ctx(tmp_path, "voice", refs))


# ---------------------------------------------------------------- subtitles


def test_split_lines_balances_and_respects_limit() -> None:
    lines = split_lines("Sunlight looks white, but it hides every color of the rainbow.")
    assert len(lines) == 2 and all(len(x) <= MAX_LINE for x in lines)
    assert split_lines("Mystery solved!") == ["Mystery solved!"]


def test_subtitles_match_script_and_follow_rules(tmp_path: Path) -> None:
    refs = upstream(tmp_path)
    voice = VoiceStage(FakeTTS(), perfect_stt(tmp_path, refs)).run(
        ctx(tmp_path, "voice", refs)).output_refs
    out = SubtitlesStage().run(ctx(tmp_path, "subtitles", {"voice": voice})).output_refs
    srt = (tmp_path / "content" / out["srt"]).read_text(encoding="utf-8")
    vtt = (tmp_path / "content" / out["vtt"]).read_text(encoding="utf-8")
    assert srt.startswith("1\n00:00:00,000 --> ") and vtt.startswith("WEBVTT")
    assert "<v Lipa>" in vtt and "<v Arka>" in vtt
    manifest = VoiceManifest.model_validate_json(
        (tmp_path / "content" / voice["path"]).read_text(encoding="utf-8"))
    cues = build_cues(manifest)
    assert len(cues) == out["cues"]
    for a, b in zip(cues, cues[1:], strict=False):
        assert a.end <= b.start + 1e-6  # no overlaps
    for c in cues:
        assert len(c.lines) <= 2 and all(len(x) <= MAX_LINE for x in c.lines)
        assert c.end - c.start >= 0.999 or c.end == cues[cues.index(c) + 1].start


def test_end_to_end_media_lane(tmp_path: Path) -> None:
    """LLM lane, owner approval, then the media lane: voice + subtitles succeed."""
    from contextlib import contextmanager

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from factory.config import PublicationMode
    from factory.db import Base
    from factory.db.models import Episode, EpisodeStatus, JobStatus, Lane, ProductionJob
    from factory.pipeline.runner import Worker
    from factory.schemas.review import ScriptReviewDraft
    from factory.schemas.script import ScriptDraft
    from factory.services import approve_stage, create_episode_from_brief
    from factory.workflow import build_workflow
    from helpers import storyboard_for

    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope():  # type: ignore[no-untyped-def]
        s = maker()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    settings = Settings(content_dir=tmp_path / "content", library_dir=tmp_path / "library",
                        publication_mode=PublicationMode.APPROVAL_REQUIRED)
    script_holder: dict = {}

    def responder(req):  # type: ignore[no-untyped-def]
        if req.schema is ScriptDraft:
            return good_draft()
        if req.schema is ScriptReviewDraft:
            return pass_review()
        return storyboard_for(script_holder["script"])

    stt = FakeSTT()
    wf = build_workflow(FakeLLM(responder=responder), FakeTTS(), stt)
    with scope() as s:
        ep_id = create_episode_from_brief(s, write_brief(tmp_path / "b.yaml"), settings, wf).id
    llm_worker = Worker(Lane.LLM, wf, scope, settings, worker_id="l")
    media_worker = Worker(Lane.MEDIA, wf, scope, settings, worker_id="m")
    llm_worker.run_until_idle()
    with scope() as s:
        script_job = s.scalars(select(ProductionJob).where(ProductionJob.stage == "script")).one()
        script = Script.model_validate_json(
            (tmp_path / "content" / script_job.output_refs["path"]).read_text(encoding="utf-8"))
        script_holder["script"] = script
        stt.by_file = {ln.line_id: ln.text for ln in script.lines}
        assert media_worker.run_once() is None  # voice waits for the approval gate
        approve_stage(s, s.get(Episode, ep_id), "script_validate", wf, "owner")
    llm_worker.run_until_idle()
    media_worker.run_until_idle()
    with scope() as s:
        jobs = {j.stage: j.status for j in s.scalars(select(ProductionJob))}
        assert jobs.pop("render_scenes") is JobStatus.QUEUED  # render lane: next step
        assert jobs.pop("assemble") is JobStatus.PENDING
        assert jobs.pop("qa") is JobStatus.PENDING
        assert set(jobs.values()) == {JobStatus.SUCCEEDED}, jobs  # incl. timing
        assert s.get(Episode, ep_id).status is EpisodeStatus.IN_PRODUCTION
