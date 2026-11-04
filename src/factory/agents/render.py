"""`render_scenes` stage: one muted H.264 clip per scene via the Remotion render server.

Clips are cached by (renderer code hash, scene plan, quality): editing one scene, or
re-running after a crash, only renders what changed. Quality comes from settings:
preview = 960x540 (crf 26) for review, final = 1920x1080 (crf 18).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from factory.agents.common import content_dir, load_upstream
from factory.db.models import Lane
from factory.media import ffmpeg
from factory.media.remotion import RemotionRenderer, RenderError, code_hash
from factory.pipeline import (
    PermanentStageError,
    RetryableStageError,
    Stage,
    StageContext,
    StageResult,
)
from factory.schemas.renderplan import RenderPlan

QUALITY = {"preview": {"scale": 0.5, "crf": 26}, "final": {"scale": 1.0, "crf": 18}}

RendererFactory = Callable[[], Any]


class RenderScenesStage(Stage):
    name = "render_scenes"
    lane = Lane.RENDER
    version = "1"
    depends_on = ("timing",)
    max_attempts = 2

    def __init__(self, renderer_factory: RendererFactory | None = None,
                 code_hash_fn: Callable[[], str] = code_hash):
        self.renderer_factory = renderer_factory or RemotionRenderer
        self.code_hash_fn = code_hash_fn

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        return {"timing": ctx.upstream["timing"]["sha256"], "code": self.code_hash_fn(),
                "quality": ctx.settings.render_quality}

    def run(self, ctx: StageContext) -> StageResult:
        plan = load_upstream(ctx, "timing", RenderPlan)
        quality = ctx.settings.render_quality
        q = QUALITY[quality]
        width, height = int(plan.width * q["scale"]), int(plan.height * q["scale"])
        cdir = content_dir(ctx)
        cache = Path(ctx.settings.library_dir) / "cache" / "render"
        cache.mkdir(parents=True, exist_ok=True)
        out_dir = ctx.workdir / quality
        out_dir.mkdir(parents=True, exist_ok=True)
        code = self.code_hash_fn()

        clips, todo = [], []
        for scene in plan.scenes:
            key = hashlib.sha256(json.dumps(
                [code, quality, scene.model_dump()], sort_keys=True).encode()).hexdigest()
            cached = cache / f"{key}.mp4"
            clips.append((scene, cached, out_dir / f"{scene.scene_id}.mp4"))
            if not cached.exists():
                todo.append((scene, cached))

        timings: dict[str, int] = {}
        if todo:
            try:
                with self.renderer_factory() as renderer:
                    for scene, cached in todo:
                        timings[scene.scene_id] = renderer.render(
                            "Scene", {"scene": scene.model_dump()}, cached,
                            scale=q["scale"], crf=q["crf"])
            except RenderError as exc:
                raise RetryableStageError(str(exc)) from exc

        problems, refs = [], []
        for scene, cached, dest in clips:
            shutil.copyfile(cached, dest)
            info = ffmpeg.video_info(dest)
            expected = scene.duration_frames / plan.fps
            if abs(info["duration"] - expected) > 1.5 / plan.fps:
                problems.append(f"{scene.scene_id}: {info['duration']:.2f}s, expected "
                                f"{expected:.2f}s")
            if (info.get("width"), info.get("height")) != (width, height):
                problems.append(f"{scene.scene_id}: {info.get('width')}x{info.get('height')}, "
                                f"expected {width}x{height}")
            refs.append({"scene_id": scene.scene_id,
                         "file": dest.resolve().relative_to(cdir.resolve()).as_posix(),
                         "render_ms": timings.get(scene.scene_id), "cached": scene.scene_id
                         not in timings})
        if problems:
            for _, cached, _ in clips:  # don't keep suspect clips in the cache
                cached.unlink(missing_ok=True)
            raise PermanentStageError("scene clips failed checks: " + "; ".join(problems))
        total_ms = sum(v for v in timings.values() if v)
        rendered_s = sum(s.duration_frames for s, _ in todo) / plan.fps if todo else 0
        return StageResult({"quality": quality, "width": width, "height": height,
                            "clips": refs, "rendered": len(todo), "cached": len(clips) - len(todo),
                            "render_s": round(total_ms / 1000, 1),
                            "realtime_factor": round(rendered_s / (total_ms / 1000), 3)
                            if total_ms else None})
