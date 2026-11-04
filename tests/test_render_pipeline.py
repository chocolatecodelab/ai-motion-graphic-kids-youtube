"""timing -> render_scenes -> assemble with a fake renderer (real FFmpeg, no Remotion)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from factory.agents.assemble import AssembleStage
from factory.agents.brief import BriefStage
from factory.agents.render import RenderScenesStage
from factory.agents.script import ScriptStage
from factory.agents.storyboard import StoryboardStage
from factory.agents.subtitles import SubtitlesStage
from factory.agents.timing import TimingStage, mouth_curve, theme_for
from factory.agents.voice import VoiceStage
from factory.config import Settings
from factory.media import ffmpeg
from factory.pipeline import PermanentStageError, StageContext
from factory.providers.llm.fake import FakeLLM
from factory.schemas.renderplan import RenderPlan
from factory.schemas.script import Script
from fakes_media import FakeSTT, FakeTTS
from helpers import good_draft, storyboard_for, write_brief

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")


def ctx(tmp_path: Path, stage: str, upstream: dict | None = None,
        quality: str = "preview") -> StageContext:
    s = Settings(content_dir=tmp_path / "content", library_dir=tmp_path / "library",
                 render_quality=quality)
    return StageContext(episode_id=uuid.uuid4(), job_id=uuid.uuid4(), stage=stage, attempt=1,
                        settings=s, workdir=tmp_path / "content" / "ep" / stage,
                        upstream=upstream or {})


class FakeRenderer:
    """Writes a solid-colour clip of the exact scene duration and size via FFmpeg."""

    renders = 0

    def __enter__(self) -> FakeRenderer:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def render(self, composition: str, props: dict, out: Path, scale: float = 1.0,
               crf: int = 20) -> int:
        FakeRenderer.renders += 1
        scene = props["scene"]
        frames = scene["duration_frames"]
        w, h = int(1920 * scale), int(1080 * scale)
        ffmpeg.run(["-f", "lavfi", "-i", f"color=c=#243B75:s={w}x{h}:r=30",
                    "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(out)])
        return 100


@pytest.fixture
def chain(tmp_path: Path) -> dict:
    write_brief(tmp_path / "content" / "ep" / "inputs" / "brief.yaml")
    up: dict = {"brief": BriefStage().run(ctx(tmp_path, "brief")).output_refs}
    up["script"] = ScriptStage(FakeLLM([good_draft()])).run(ctx(tmp_path, "script", up)).output_refs
    script = Script.model_validate_json(
        (tmp_path / "content" / up["script"]["path"]).read_text(encoding="utf-8"))
    up["script_validate"] = {"verdict": "pass"}
    up["storyboard"] = StoryboardStage(FakeLLM([storyboard_for(script)])).run(
        ctx(tmp_path, "storyboard", up)).output_refs
    stt = FakeSTT({ln.line_id: ln.text for ln in script.lines})
    up["voice"] = VoiceStage(FakeTTS(), stt).run(ctx(tmp_path, "voice", up)).output_refs
    up["subtitles"] = SubtitlesStage().run(ctx(tmp_path, "subtitles", up)).output_refs
    return up


def test_theme_mapping() -> None:
    assert theme_for("Dusty red Martian landscape") == "mars"
    assert theme_for("Calm hilltop at sunset") == "sunset"
    assert theme_for("Among scattered air molecules") == "air"
    assert theme_for("Cozy grandparent's attic with a round window") == "attic"
    assert theme_for("something else") == "studio"


def test_timing_builds_frame_accurate_plan(tmp_path: Path, chain: dict) -> None:
    out = TimingStage().run(ctx(tmp_path, "timing", chain)).output_refs
    plan = RenderPlan.model_validate_json(
        (tmp_path / "content" / out["path"]).read_text(encoding="utf-8"))
    assert plan.total_frames == sum(s.duration_frames for s in plan.scenes)
    assert plan.scene_start_frames[0] == 0
    for scene in plan.scenes:
        last_end = 0
        for ln in scene.lines:
            assert ln.start_frame >= last_end and len(ln.mouth) == ln.end_frame - ln.start_frame
            assert ln.end_frame <= scene.duration_frames
            last_end = ln.end_frame
        assert scene.shots[0].start_frame == 0
        assert scene.shots[-1].end_frame == scene.duration_frames
    assert plan.scenes[0].transition_in.type == "fade"
    assert plan.scenes[2].transition_out.type == "compass_portal"  # from the storyboard
    assert plan.scenes[3].transition_in.type == "compass_portal"
    assert len(plan.audio) == 14
    srt = (tmp_path / "content" / out["srt"]).read_text(encoding="utf-8")
    assert srt.startswith("1\n")


def test_mouth_curve_tracks_loudness(tmp_path: Path) -> None:
    import numpy as np

    from factory.media.audio import write_wav

    sr = 24_000
    tone = 0.4 * np.sin(2 * np.pi * 200 * np.arange(sr) / sr)
    audio = np.concatenate([np.zeros(sr // 2), tone, np.zeros(sr // 2)]).astype(np.float32)
    write_wav(tmp_path / "x.wav", audio, sr)
    curve = mouth_curve(tmp_path / "x.wav", 60)
    assert max(curve[:12]) == 0 and max(curve[20:40]) > 0.8


def test_render_and_assemble_episode(tmp_path: Path, chain: dict) -> None:
    chain["timing"] = TimingStage().run(ctx(tmp_path, "timing", chain)).output_refs
    FakeRenderer.renders = 0
    stage = RenderScenesStage(renderer_factory=FakeRenderer, code_hash_fn=lambda: "code-v1")
    chain["render_scenes"] = stage.run(ctx(tmp_path, "render_scenes", chain)).output_refs
    assert chain["render_scenes"]["width"] == 960 and FakeRenderer.renders == 6
    # Second run: every scene comes from the render cache.
    again = stage.run(ctx(tmp_path, "render_scenes", chain)).output_refs
    assert again["cached"] == 6 and FakeRenderer.renders == 6

    out = AssembleStage().run(ctx(tmp_path, "assemble", chain)).output_refs
    video = tmp_path / "content" / out["video"]
    info = ffmpeg.video_info(video)
    assert info["vcodec"] == "h264" and info["acodec"] == "aac"
    assert abs(out["loudness_lufs"] - (-14)) <= 1.0
    assert out["srt"].endswith("en.srt") and (tmp_path / "content" / out["srt"]).exists()


def test_render_rejects_wrong_duration(tmp_path: Path, chain: dict) -> None:
    chain["timing"] = TimingStage().run(ctx(tmp_path, "timing", chain)).output_refs

    class ShortRenderer(FakeRenderer):
        def render(self, composition, props, out, scale=1.0, crf=20):  # type: ignore[no-untyped-def]
            props = {"scene": {**props["scene"], "duration_frames": 10}}
            return super().render(composition, props, out, scale, crf)

    stage = RenderScenesStage(renderer_factory=ShortRenderer, code_hash_fn=lambda: "code-v2")
    with pytest.raises(PermanentStageError, match="expected"):
        stage.run(ctx(tmp_path, "render_scenes", chain))
    assert not list((tmp_path / "library" / "cache" / "render").glob("*.mp4"))
