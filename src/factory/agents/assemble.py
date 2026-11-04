"""`assemble` stage: scene clips + voice-over -> episode MP4.

- Video: concatenation of the scene clips (stream copy, no quality loss).
- Audio: every voice line mixed at its planned start, normalised to -14 LUFS / -1 dBTP
  (EBU R128, two-pass), AAC 192 kbit/s 48 kHz.
- Checks: duration matches the plan, H.264 + AAC, integrated loudness within ±1 LU.
Music beds and SFX are mixed in a later iteration (procedural audio, DECISIONS D2).
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from factory.agents.common import content_dir, load_upstream
from factory.db.models import Lane
from factory.media import audio as A
from factory.media import ffmpeg
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.schemas.renderplan import RenderPlan

SAMPLE_RATE = 24_000
TARGET_LUFS = -14.0


class AssembleStage(Stage):
    name = "assemble"
    lane = Lane.MEDIA
    version = "1"
    depends_on = ("timing", "render_scenes")
    max_attempts = 2

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        clips = ctx.upstream["render_scenes"].get("clips", [])
        return {"timing": ctx.upstream["timing"]["sha256"],
                "clips": [c["file"] for c in clips],
                "quality": ctx.upstream["render_scenes"].get("quality")}

    def run(self, ctx: StageContext) -> StageResult:
        plan = load_upstream(ctx, "timing", RenderPlan)
        render = ctx.upstream["render_scenes"]
        quality = render["quality"]
        cdir = content_dir(ctx)
        ctx.workdir.mkdir(parents=True, exist_ok=True)
        clips = [cdir / c["file"] for c in render["clips"]]
        missing = [str(c) for c in clips if not c.exists()]
        if missing:
            raise PermanentStageError(f"missing scene clips: {missing[:3]}")

        video = ctx.workdir / f"video_{quality}.mp4"
        ffmpeg.concat(clips, video)

        total_s = plan.total_frames / plan.fps
        mix = np.zeros(int(round(total_s * SAMPLE_RATE)) + SAMPLE_RATE, dtype=np.float32)
        for cue in plan.audio:
            audio, sr = A.read_wav(cdir / cue.file)
            if sr != SAMPLE_RATE:
                raise PermanentStageError(f"{cue.line_id}: sample rate {sr}, expected "
                                          f"{SAMPLE_RATE}")
            start = int(round(cue.start_s * SAMPLE_RATE))
            end = min(len(mix), start + len(audio))
            mix[start:end] += audio[: end - start]
        mix = mix[: int(round(total_s * SAMPLE_RATE))]
        peak = A.peak(mix)
        if peak > 0.99:
            mix = mix * (0.99 / peak)
        raw = ctx.workdir / "vo_mix_raw.wav"
        A.write_wav(raw, mix, SAMPLE_RATE)
        norm = ctx.workdir / "vo_mix.wav"
        ffmpeg.loudnorm_two_pass(raw, norm, integrated=TARGET_LUFS)

        out = ctx.workdir / f"episode_{quality}.mp4"
        ffmpeg.run(["-i", str(video), "-i", str(norm), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-t", f"{total_s:.3f}", "-movflags", "+faststart", str(out)])
        raw.unlink(missing_ok=True)
        video.unlink(missing_ok=True)

        info = ffmpeg.video_info(out)
        loud = ffmpeg.measure_loudness(out)
        problems = []
        if abs(info["duration"] - total_s) > 0.15:
            problems.append(f"duration {info['duration']:.2f}s vs plan {total_s:.2f}s")
        if info.get("vcodec") != "h264" or info.get("acodec") != "aac":
            problems.append(f"codecs {info.get('vcodec')}/{info.get('acodec')}")
        if not abs(loud["integrated_lufs"] - TARGET_LUFS) <= 1.0:
            problems.append(f"loudness {loud['integrated_lufs']} LUFS")
        if problems:
            raise PermanentStageError("assembled episode failed checks: " + "; ".join(problems))

        subs = {}
        for key in ("subtitles_srt", "subtitles_vtt"):
            src = getattr(plan, key)
            if src:
                dest = ctx.workdir / Path(src).name
                shutil.copyfile(cdir / src, dest)
                subs[key.split("_")[1]] = dest.resolve().relative_to(cdir.resolve()).as_posix()
        return StageResult({
            "quality": quality, "video": out.resolve().relative_to(cdir.resolve()).as_posix(),
            "duration_s": round(info["duration"], 2), "width": info.get("width"),
            "height": info.get("height"), "loudness_lufs": loud["integrated_lufs"],
            "true_peak_dbtp": loud["true_peak_dbtp"], **subs,
        })
