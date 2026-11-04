"""brief / script / script_validate / storyboard stages with FakeLLM (offline)."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from factory.agents.brief import BriefStage
from factory.agents.script import ScriptStage, build_script, check_script
from factory.agents.script_validate import ScriptValidateStage
from factory.agents.storyboard import check_storyboard
from factory.config import PublicationMode, Settings
from factory.db import Base
from factory.db.models import Approval, Episode, EpisodeStatus, JobStatus, Lane, ProductionJob
from factory.pipeline import PermanentStageError, RevisionRequested, StageContext
from factory.pipeline.runner import Worker
from factory.providers.llm import LLMRequest
from factory.providers.llm.fake import FakeLLM
from factory.schemas.brief import TopicBrief
from factory.schemas.review import ScriptReviewDraft
from factory.schemas.script import Script, ScriptDraft
from factory.schemas.storyboard import StoryboardDraft
from factory.services import approve_stage, create_episode_from_brief
from factory.workflow import build_workflow
from helpers import good_draft, pass_review, pilot_brief_dict, storyboard_for, write_brief


def ctx_for(tmp_path: Path, stage: str, upstream: dict | None = None) -> StageContext:
    settings = Settings(content_dir=tmp_path / "content")
    return StageContext(episode_id=uuid.uuid4(), job_id=uuid.uuid4(), stage=stage, attempt=1,
                        settings=settings, workdir=tmp_path / "content" / "ep" / stage,
                        upstream=upstream or {})


def run_brief(tmp_path: Path, **kw) -> dict:  # type: ignore[no-untyped-def]
    write_brief(tmp_path / "content" / "ep" / "inputs" / "brief.yaml", **kw)
    return BriefStage().run(ctx_for(tmp_path, "brief")).output_refs


def brief_model() -> TopicBrief:
    return TopicBrief.model_validate(pilot_brief_dict())


def script_model(draft: dict | None = None) -> Script:
    return build_script(ScriptDraft.model_validate(draft or good_draft()), "sky", 1,
                        ctx_for(Path("."), "script"))


# ---------------------------------------------------------------- brief


def test_real_pilot_brief_is_valid(tmp_path: Path) -> None:
    ref = run_brief(tmp_path, min_s=120, max_s=180)
    assert ref["claims"] == 9 and ref["path"].endswith("brief.v1.json")


def test_brief_rejects_single_source_key_claim(tmp_path: Path) -> None:
    data = pilot_brief_dict()
    data["claims"][0]["evidence"] = data["claims"][0]["evidence"][:1]
    path = tmp_path / "content" / "ep" / "inputs" / "brief.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(PermanentStageError, match="C01 has fewer than 2"):
        BriefStage().run(ctx_for(tmp_path, "brief"))


# ---------------------------------------------------------------- script checks


def test_good_script_passes_checks() -> None:
    script = script_model()
    assert check_script(script, brief_model()) == []
    assert [ln.line_id for ln in script.lines][:3] == ["S01-L01", "S01-L02", "S02-L01"]
    assert script.readability["fk_grade"] <= 6.5


@pytest.mark.parametrize(
    ("mutate", "expect"),
    [
        (lambda d: d["scenes"][0]["lines"].insert(0, {
            "speaker": "kai", "text": "Hey guys, let's dive in!", "emotion": "excited",
            "claim_ids": [], "direction": ""}), "banned phrasing"),
        (lambda d: d["scenes"][1]["lines"][0].update(claim_ids=["C99"]), "unknown or unverified"),
        (lambda d: d["scenes"].reverse(), "Beats must follow"),
        (lambda d: d["scenes"][0]["lines"].insert(0, {
            "speaker": "kai", "text": " ".join(["word"] * 45) + ".", "emotion": "neutral",
            "claim_ids": [], "direction": ""}), "central question"),
        (lambda d: [s["lines"].extend(s["lines"] * 6) for s in d["scenes"]], "spoken length"),
        (lambda d: d["scenes"][3]["lines"][0].update(
            text="Electromagnetic radiation demonstrates wavelength-dependent scattering "
                 "characteristics, fundamentally attributable to molecular polarizability "
                 "interacting proportionally with oscillating electromagnetic fields."),
         "too complex"),
    ],
)
def test_script_checks_catch_defects(mutate, expect: str) -> None:  # type: ignore[no-untyped-def]
    draft = copy.deepcopy(good_draft())
    mutate(draft)
    issues = check_script(script_model(draft), brief_model())
    assert any(expect in i for i in issues), issues


# ---------------------------------------------------------------- script stage


def test_script_stage_revises_then_succeeds(tmp_path: Path) -> None:
    brief_ref = run_brief(tmp_path)
    bad = copy.deepcopy(good_draft())
    bad["scenes"][1]["lines"][0]["claim_ids"] = ["C42"]
    llm = FakeLLM([bad, good_draft()])
    out = ScriptStage(llm).run(ctx_for(tmp_path, "script", {"brief": brief_ref})).output_refs
    assert out["revisions"] == 1
    assert "C42" in llm.requests[1].prompt  # failed check fed back to the model
    assert llm.requests[0].tier.value == "high"
    md = (tmp_path / "content" / out["markdown"]).read_text(encoding="utf-8")
    assert "S04" in md and "[C03]" in md


def test_script_stage_gives_up_after_two_revisions(tmp_path: Path) -> None:
    brief_ref = run_brief(tmp_path)
    bad = copy.deepcopy(good_draft())
    bad["scenes"][1]["lines"][0]["claim_ids"] = ["C42"]
    with pytest.raises(PermanentStageError, match="after 2 revisions"):
        ScriptStage(FakeLLM([bad, bad, bad])).run(
            ctx_for(tmp_path, "script", {"brief": brief_ref}))
    assert list((tmp_path / "content" / "ep" / "script").glob("script_failed.v1.json"))


# ---------------------------------------------------------------- review


def _script_refs(tmp_path: Path) -> dict:
    brief_ref = run_brief(tmp_path)
    script_ref = ScriptStage(FakeLLM([good_draft()])).run(
        ctx_for(tmp_path, "script", {"brief": brief_ref})).output_refs
    return {"brief": brief_ref, "script": script_ref}


def test_review_fails_on_unsupported_statement(tmp_path: Path) -> None:
    refs = _script_refs(tmp_path)
    review = pass_review()
    review["unsupported_statements"] = [{"line_id": "S04-L02", "text": "Air is pink.",
                                         "reason": "not in claims", "severity": "major"}]
    stage = ScriptValidateStage(FakeLLM([review, review, review]))
    ctx = ctx_for(tmp_path, "script_validate", refs)
    # Two automatic revision requests with written feedback...
    for n in (1, 2):
        with pytest.raises(RevisionRequested, match=f"revision {n}/2") as exc:
            stage.run(ctx)
        assert exc.value.target == "script"
        fb = (tmp_path / "content" / "ep" / "inputs" / "feedback" / f"script.v{n}.md")
        assert "S04-L02" in fb.read_text(encoding="utf-8")
    # ...then it stops and waits for a human.
    with pytest.raises(PermanentStageError, match="after 2 automatic revisions"):
        stage.run(ctx)
    assert list((tmp_path / "content" / "ep" / "script_validate").glob("review.v3.md"))


def test_safety_critical_review_is_never_auto_revised(tmp_path: Path) -> None:
    refs = _script_refs(tmp_path)
    review = pass_review()
    review["issues"].append({"severity": "critical", "category": "safety", "line_id": "S03-L01",
                             "detail": "Encourages looking at the Sun.", "suggestion": "Cut."})
    with pytest.raises(PermanentStageError, match="safety-critical"):
        ScriptValidateStage(FakeLLM([review])).run(ctx_for(tmp_path, "script_validate", refs))


def test_minor_unsupported_statement_is_a_warning_not_a_block(tmp_path: Path) -> None:
    refs = _script_refs(tmp_path)
    review = pass_review()
    review["unsupported_statements"] = [{"line_id": "S02-L01", "text": "Light comes from the Sun.",
                                         "reason": "everyday knowledge", "severity": "minor"}]
    out = ScriptValidateStage(FakeLLM([review])).run(
        ctx_for(tmp_path, "script_validate", refs)).output_refs
    assert out["verdict"] == "pass" and out["warnings"] == 1
    md = (tmp_path / "content" / out["markdown"]).read_text(encoding="utf-8")
    assert "Check before approving" in md and "S02-L01" in md


def test_review_pass(tmp_path: Path) -> None:
    refs = _script_refs(tmp_path)
    out = ScriptValidateStage(FakeLLM([pass_review()])).run(
        ctx_for(tmp_path, "script_validate", refs)).output_refs
    assert out["verdict"] == "pass" and out["min_score"] == 4


def test_review_requires_approval_in_manual_and_approval_modes() -> None:
    stage = ScriptValidateStage(FakeLLM())
    assert stage.requires_approval(PublicationMode.APPROVAL_REQUIRED)
    assert stage.requires_approval(PublicationMode.MANUAL)
    assert not stage.requires_approval(PublicationMode.FULL_AUTOMATION)


# ---------------------------------------------------------------- storyboard


def test_good_storyboard_passes() -> None:
    script = script_model()
    draft = StoryboardDraft.model_validate(storyboard_for(script))
    assert check_storyboard(draft, script, brief_model()) == []


def test_storyboard_html_shows_every_scene_and_escapes_text() -> None:
    from factory.schemas.storyboard import Storyboard
    from factory.storyboard_html import render_storyboard_html

    draft = copy.deepcopy(good_draft())
    draft["scenes"][0]["lines"][0]["text"] = "Why is the sky blue? <script>alert(1)</script>"
    script = script_model(draft)
    board = Storyboard(episode_slug="sky", script_version=1,
                       scenes=StoryboardDraft.model_validate(storyboard_for(script)).scenes,
                       total_duration_s=60, catalogue_version="c", rig_version="r")
    html = render_storyboard_html(board, script, brief_model(), version=3)
    for s in board.scenes:
        assert f'id="{s.scene_id}"' in html and f'href="#{s.scene_id}"' in html
    for ln in script.lines[1:]:
        assert ln.text.replace("'", "&#x27;") in html
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert 'id="claim-C05"' in html and 'href="#claim-C05"' in html
    assert "storyboard v3" in html and "spaceplace.nasa.gov" in html
    assert "<audio" not in html  # no voice yet

    voiced = render_storyboard_html(board, script, brief_model(), version=3,
                                    audio={"S01-L02": ("../voice/lines/S01-L02.wav", 2.1)},
                                    preview_src="../voice/vo_preview.wav")
    assert 'src="../voice/lines/S01-L02.wav"' in voiced and "2.1s (voiced)" in voiced
    assert "Full voice-over preview" in voiced


def test_numbers_allowed_when_illustrative_or_sourced() -> None:
    script = script_model()
    board = storyboard_for(script)
    board["scenes"][4]["motion_graphics"] += [
        {"component": "BarGrow", "illustrative": True,
         "props": {"items": [{"label": "violet", "value": 1}, {"label": "blue", "value": 2}]}},
        {"component": "ScaleCompare", "claim_ids": ["C04"],
         "props": {"items": [{"label": "molecule", "relative_size": 1}]}},
    ]
    assert check_storyboard(StoryboardDraft.model_validate(board), script, brief_model()) == []


@pytest.mark.parametrize(
    ("mutate", "expect"),
    [
        (lambda b: b["scenes"][0]["characters"][0].update(pose="backflip"), "unknown pose"),
        (lambda b: b["scenes"][3]["motion_graphics"].append({"component": "Fireworks"}),
         "unknown component"),
        (lambda b: b["scenes"][1]["line_ids"].pop(), "exactly once"),
        (lambda b: b["scenes"][2].update(duration_s=1.0), "lines need"),
        (lambda b: b["scenes"][0]["characters"].pop(), "must be in `characters`"),
        (lambda b: b["scenes"][4]["motion_graphics"].append(
            {"component": "BarGrow", "props": {"items": [{"label": "violet", "value": 3}]}}),
         "no verified claim states"),
        (lambda b: b["scenes"][4]["motion_graphics"].append(
            {"component": "Counter", "props": {"to": 5}, "claim_ids": ["C77"]}),
         "cites unknown claims"),
    ],
)
def test_storyboard_checks_catch_defects(mutate, expect: str) -> None:  # type: ignore[no-untyped-def]
    script = script_model()
    board = storyboard_for(script)
    mutate(board)
    issues = check_storyboard(StoryboardDraft.model_validate(board), script, brief_model())
    assert any(expect in i for i in issues), issues


# ---------------------------------------------------------------- end to end (queue + worker)


def responder(request: LLMRequest) -> dict:  # type: ignore[type-arg]
    if request.schema is ScriptDraft:
        return good_draft()
    if request.schema is ScriptReviewDraft:
        return pass_review()
    if request.schema is StoryboardDraft:
        return storyboard_for(script_model())
    raise AssertionError(request.schema)


def test_review_rejection_triggers_script_rewrite_end_to_end(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'loop.db').as_posix()}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope() -> Iterator[Session]:
        s = maker()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    failing = pass_review()
    failing["unsupported_statements"] = [{"line_id": "S07-L01", "text": "Mars is flipped.",
                                          "reason": "implies a mechanism", "severity": "major"}]
    reviews = iter([failing, pass_review()])

    def loop_responder(request: LLMRequest) -> dict:  # type: ignore[type-arg]
        if request.schema is ScriptReviewDraft:
            return next(reviews)
        return responder(request)

    settings = Settings(content_dir=tmp_path / "content",
                        publication_mode=PublicationMode.APPROVAL_REQUIRED)
    llm = FakeLLM(responder=loop_responder)
    wf = build_workflow(llm)
    with scope() as s:
        create_episode_from_brief(s, write_brief(tmp_path / "brief.yaml"), settings, wf)
    Worker(Lane.LLM, wf, scope, settings, worker_id="t").run_until_idle()

    with scope() as s:
        jobs = {j.stage: j.status for j in s.scalars(select(ProductionJob))}
        script_job = s.scalars(select(ProductionJob).where(ProductionJob.stage == "script")).one()
        assert script_job.output_refs["version"] == 2
    assert jobs["script_validate"] is JobStatus.AWAITING_APPROVAL
    assert [r.schema.__name__ for r in llm.requests] == [
        "ScriptDraft", "ScriptReviewDraft", "ScriptDraft", "ScriptReviewDraft"]
    rewrite_prompt = llm.requests[2].prompt
    assert "independent reviewer rejected" in rewrite_prompt and "S07-L01" in rewrite_prompt


def test_end_to_end_with_approval_gate(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'e2e.db').as_posix()}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope() -> Iterator[Session]:
        s = maker()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    settings = Settings(content_dir=tmp_path / "content",
                        publication_mode=PublicationMode.APPROVAL_REQUIRED)
    llm = FakeLLM(responder=responder)
    wf = build_workflow(llm)
    brief = write_brief(tmp_path / "brief.yaml")
    with scope() as s:
        ep_id = create_episode_from_brief(s, brief, settings, wf).id

    worker = Worker(Lane.LLM, wf, scope, settings, worker_id="t")
    worker.run_until_idle()
    with scope() as s:
        jobs = {j.stage: j.status for j in s.scalars(select(ProductionJob))}
        assert jobs == {"brief": JobStatus.SUCCEEDED, "script": JobStatus.SUCCEEDED,
                        "script_validate": JobStatus.AWAITING_APPROVAL,
                        "storyboard": JobStatus.PENDING, "voice": JobStatus.PENDING,
                        "subtitles": JobStatus.PENDING}
        ep = s.get(Episode, ep_id)
        assert ep.status is EpisodeStatus.AWAITING_APPROVAL
        approve_stage(s, ep, "script_validate", wf, "owner", "Looks great")

    worker.run_until_idle()
    with scope() as s:
        # LLM lane done; voice is now queued for the media lane (tested in test_voice.py).
        assert s.get(Episode, ep_id).status is EpisodeStatus.IN_PRODUCTION
        voice_job = s.scalars(select(ProductionJob).where(ProductionJob.stage == "voice")).one()
        assert voice_job.status is JobStatus.QUEUED
        board_job = s.scalars(select(ProductionJob).where(
            ProductionJob.stage == "storyboard")).one()
        assert board_job.output_refs["scenes"] == 6
        html = tmp_path / "content" / board_job.output_refs["html"]
        assert html.exists() and "S06" in html.read_text(encoding="utf-8")
        assert s.scalars(select(Approval)).one().decided_by == "owner"
    assert [r.schema.__name__ for r in llm.requests] == [
        "ScriptDraft", "ScriptReviewDraft", "StoryboardDraft"]

    with scope() as s, pytest.raises(ValueError, match="already has episode"):
        create_episode_from_brief(s, brief, settings, wf)
