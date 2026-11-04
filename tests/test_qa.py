"""Seeded-defect tests (docs/TESTING_STRATEGY.md): QA must catch each injected defect."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from factory.media import ffmpeg
from factory.qa import checks as C

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")


def make_video(path: Path, seconds: float = 6.0, size: str = "640x360", black: tuple | None = None,
               silence: tuple | None = None, gain: float = 0.3, clip: bool = False) -> Path:
    vf = "null"
    if black:
        vf = (f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:"
              f"enable='between(t,{black[0]},{black[1]})'")
    af = f"volume={gain}"
    if silence:
        af += f",volume=enable='between(t,{silence[0]},{silence[1]})':volume=0"
    if clip:
        af = "volume=12,alimiter=limit=1:level=false:attack=0.1:release=1"
    ffmpeg.run(["-f", "lavfi", "-i", f"testsrc2=s={size}:r=30:d={seconds}",
                "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={seconds}",
                "-vf", vf, "-af", af, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-shortest", str(path)])
    return path


EXPECTED = {"width": 640, "height": 360, "fps": 30}


def ids(results: list[C.Check], severity: str) -> set[str]:
    return {r.id for r in results if r.severity == severity}


def test_clean_video_passes_technical_checks(tmp_path: Path) -> None:
    v = make_video(tmp_path / "clean.mp4")
    results = [*C.check_spec(v, EXPECTED, 6.0), C.check_decode(v)]
    s = C.scan(v)
    results += [C.check_black(s), *C.check_silence(s, [(0.5, 5.5)])]
    assert ids(results, "critical") == set(), [r.detail for r in results]


def test_seeded_black_frames_are_critical(tmp_path: Path) -> None:
    v = make_video(tmp_path / "black.mp4", black=(2, 4))
    check = C.check_black(C.scan(v))
    assert check.severity == "critical" and "2.0" in check.detail
    assert check.fix_stage == "render_scenes"


def test_seeded_wrong_orientation_is_critical(tmp_path: Path) -> None:
    v = make_video(tmp_path / "portrait.mp4", size="360x640")
    assert "spec.resolution" in ids(C.check_spec(v, EXPECTED, 6.0), "critical")


def test_seeded_duration_drift_is_critical(tmp_path: Path) -> None:
    v = make_video(tmp_path / "short.mp4", seconds=4.0)
    assert "spec.duration" in ids(C.check_spec(v, EXPECTED, 6.0), "critical")


def test_seeded_clipping_is_critical(tmp_path: Path) -> None:
    v = make_video(tmp_path / "clipped.mp4", clip=True)
    results = C.check_loudness(v)
    assert "audio.true_peak" in ids(results, "critical"), [r.detail for r in results]


def test_seeded_dropout_inside_a_line_is_critical(tmp_path: Path) -> None:
    v = make_video(tmp_path / "dropout.mp4", silence=(2.0, 3.2))
    s = C.scan(v)
    results = C.check_silence(s, speech=[(1.0, 5.0)])  # a voice line spans the gap
    assert "audio.dropouts" in ids(results, "critical")
    # The same silence between two lines is not a dropout.
    between = C.check_silence(s, speech=[(0.2, 1.9), (3.4, 5.5)])
    assert "audio.dropouts" not in ids(between, "critical")


def test_seeded_wrong_vo_line_is_caught_by_wer() -> None:
    script = "Sunlight looks white but it hides every colour of the rainbow. Blue waves are short."
    heard_ok = "sunlight looks white but it hides every color of the rainbow blue waves are short"
    heard_bad = "pizza is round and cheese is yellow blue waves are short"
    assert C.check_speech(script, heard_ok).severity == "info"
    bad = C.check_speech(script, heard_bad)
    assert bad.severity == "critical" and bad.fix_stage == "voice"


def _words(cues: list[tuple[float, float, str]], offset: float) -> list[tuple[str, float, float]]:
    out = []
    for start, end, text in cues:
        ws = text.split()
        step = (end - start) / len(ws)
        out += [(w, start + offset + i * step, start + offset + (i + 1) * step)
                for i, w in enumerate(ws)]
    return out


CUES = [(1.0, 2.5, "Why is the sky blue?"), (3.0, 4.6, "Maybe someone painted it!"),
        (5.0, 7.0, "Sunlight looks white to me."), (7.5, 9.0, "Light travels in waves."),
        (9.5, 11.0, "Blue waves are short.")]


def test_subtitle_sync_passes_when_aligned() -> None:
    assert C.check_subtitle_sync(CUES, _words(CUES, 0.05)).severity == "info"


def test_seeded_subtitle_drift_is_critical() -> None:
    # Subtitles appear 800 ms before the speech they belong to.
    check = C.check_subtitle_sync(CUES, _words(CUES, 0.8))
    assert check.severity == "critical" and check.fix_stage == "timing"
    assert C.check_subtitle_sync(CUES, _words(CUES, 0.35)).severity == "warning"


def test_subtitle_text_must_match_script() -> None:
    script = " ".join(t for _, _, t in CUES)
    assert C.check_subtitle_text(CUES, script).severity == "info"
    assert C.check_subtitle_text(CUES[:-1], script).severity == "critical"


def test_srt_parsing_roundtrip() -> None:
    srt = "1\n00:00:01,000 --> 00:00:02,500\nWhy is the sky blue?\n\n2\n00:01:03,250 --> " \
          "00:01:04,000\nTwo\nlines\n"
    assert C.parse_srt(srt) == [(1.0, 2.5, "Why is the sky blue?"), (63.25, 64.0, "Two lines")]


def test_seeded_unverified_claim_and_missing_font_licence(tmp_path: Path) -> None:
    import uuid

    from factory.agents.qa import content_checks, rights_checks
    from factory.agents.script import build_script
    from factory.config import Settings
    from factory.pipeline import StageContext
    from factory.schemas.brief import TopicBrief
    from factory.schemas.script import ScriptDraft
    from factory.schemas.voice import VoiceManifest
    from helpers import good_draft, pilot_brief_dict
    draft = good_draft()
    draft["scenes"][1]["lines"][0]["claim_ids"] = ["C99"]
    ctx = StageContext(episode_id=uuid.uuid4(), job_id=uuid.uuid4(), stage="x", attempt=1,
                       settings=Settings(), workdir=tmp_path, upstream={})
    script = build_script(ScriptDraft.model_validate(draft), "sky", 1, ctx)
    brief = TopicBrief.model_validate(pilot_brief_dict())
    assert content_checks(script, brief)[0].severity == "critical"

    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "Baloo2-Variable.ttf").write_bytes(b"x")
    (fonts / "Baloo2.txt").write_text("OFL", encoding="utf-8")
    (fonts / "Mystery-Regular.ttf").write_bytes(b"x")  # no licence file
    manifest = VoiceManifest(episode_slug="sky", script_version=1, sample_rate=24000,
                             engine="kokoro", model="hexgrad/Kokoro-82M", licence="Apache-2.0",
                             stt_model="x", gap_s=0.35, lines=[], preview_file="p.wav",
                             total_speech_s=1, preview_duration_s=1, overall_wer=0)
    results = rights_checks(manifest, fonts)
    font_check = next(r for r in results if r.id == "rights.fonts")
    assert font_check.severity == "critical" and "Mystery-Regular.ttf" in font_check.detail
    bad_voice = rights_checks(manifest.model_copy(update={"licence": "CC-BY-NC-4.0"}), fonts)
    assert next(r for r in bad_voice if r.id == "rights.voice").severity == "critical"
