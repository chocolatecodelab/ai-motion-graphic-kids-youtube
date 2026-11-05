"""`assemble` stage: scene clips + voice-over -> episode MP4.

- Video: concatenation of the scene clips (stream copy, no quality loss).
- Audio at 48 kHz: every voice line at its planned start, the procedural music bed (one mood
  per scene, ducked under speech) and procedural SFX (factory.media.synth, original audio,
  DECISIONS D2). The mix is normalised to -14 LUFS / -1 dBTP (EBU R128, two-pass), AAC 192k.
- A voice-only stem is kept so QA can still find dropouts under the music.
- Checks: duration matches the plan, H.264 + AAC, integrated loudness within ±1 LU.
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
from factory.media import ffmpeg, synth
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.schemas.renderplan import RenderPlan

SAMPLE_RATE = 24_000  # voice lines
MIX_SR = synth.SR  # 48 kHz mix
TARGET_LUFS = -14.0
AUDIO_MIX_VERSION = "3"  # v3: loudness-relative pre-limiter + -1.5 dBTP headroom
PEAK_OVER_LUFS = 11.5  # limiter ceiling above integrated loudness (dB)
MUSIC_UNDER_VOICE_DB = -11.0  # bed RMS vs speech RMS before ducking (~-20 dB while speaking)
SFX_VS_VOICE_DB = -7.0


class AssembleStage(Stage):
    name = "assemble"
    lane = Lane.MEDIA
    version = "2"  # v2: music bed + SFX, 48 kHz mix, voice stem
    depends_on = ("timing", "render_scenes")
    max_attempts = 2

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        clips = ctx.upstream["render_scenes"].get("clips", [])
        return {"timing": ctx.upstream["timing"]["sha256"],
                "clips": [c["file"] for c in clips],
                "quality": ctx.upstream["render_scenes"].get("quality"),
                "audio_mix": AUDIO_MIX_VERSION}

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
        voice = self._voice_bus(plan, cdir, total_s)
        A.write_wav(ctx.workdir / "voice_stem.wav", voice, MIX_SR)
        music, sfx = mix_beds(plan, voice, total_s)
        mix = voice + music + sfx
        # Level speech to ~-23 dBFS RMS, then limit peaks to 11.5 dB above the measured loudness,
        # so linear loudnorm can lift the mix to -14 LUFS and still stay under -1.5 dBTP (room
        # for AAC overshoot). Without this, loudnorm falls back to imprecise dynamic mode.
        voiced = np.abs(voice) > 0.01
        speech_rms = float(np.sqrt(np.mean(mix[voiced] ** 2))) if voiced.any() else A.rms(mix)
        mix = mix * (10 ** (-23 / 20) / max(speech_rms, 1e-6))
        peak = A.peak(mix)
        if peak > 0.99:
            mix = mix * (0.99 / peak)
        raw = ctx.workdir / "mix_raw.wav"
        A.write_wav(raw, mix, MIX_SR)
        limited = ctx.workdir / "mix_limited.wav"
        ceiling = 10 ** ((ffmpeg.measure_loudness(raw)["integrated_lufs"] + PEAK_OVER_LUFS) / 20)
        ffmpeg.run(["-i", str(raw), "-af", f"alimiter=limit={min(1.0, max(0.0625, ceiling)):.4f}"
                    ":attack=5:release=80:level=false", str(limited)])
        norm = ctx.workdir / "mix.wav"
        ffmpeg.loudnorm_two_pass(limited, norm, integrated=TARGET_LUFS, true_peak=-1.5)
        limited.unlink(missing_ok=True)

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
            "voice_stem": (ctx.workdir / "voice_stem.wav").resolve().relative_to(
                cdir.resolve()).as_posix(),
            "music": bool(plan.music), "sfx": len(plan.sfx),
            "audio_source": "procedural (factory.media.synth), original",
        })

    @staticmethod
    def _voice_bus(plan: RenderPlan, cdir: Path, total_s: float) -> np.ndarray:
        bus = np.zeros(int(round(total_s * MIX_SR)) + MIX_SR, dtype=np.float32)
        for cue in plan.audio:
            audio, sr = A.read_wav(cdir / cue.file)
            if sr != SAMPLE_RATE:
                raise PermanentStageError(f"{cue.line_id}: sample rate {sr}, expected "
                                          f"{SAMPLE_RATE}")
            up = synth.upsample2(audio)
            start = int(round(cue.start_s * MIX_SR))
            end = min(len(bus), start + len(up))
            bus[start:end] += up[: end - start]
        return bus[: int(round(total_s * MIX_SR))]


def mix_beds(plan: RenderPlan, voice: np.ndarray, total_s: float) -> tuple[np.ndarray, np.ndarray]:
    """(ducked music bed, SFX bus) levelled against the speech level of `voice`."""
    n = voice.size
    voiced = np.abs(voice) > 0.01
    speech_rms = float(np.sqrt(np.mean(voice[voiced] ** 2))) if voiced.any() else 0.1
    music = np.zeros(n, dtype=np.float32)
    if plan.music:
        sections = [synth.Section(m.mood, m.start_s, m.end_s) for m in plan.music]
        bed = synth.music_bed(sections, total_s, seed=plan.episode_slug)[:n]
        bed_rms = float(np.sqrt(np.mean(bed ** 2))) or 1.0
        music[: bed.size] = bed * (speech_rms * 10 ** (MUSIC_UNDER_VOICE_DB / 20) / bed_rms)
        music *= synth.duck_gain(voice)
    sfx = np.zeros(n, dtype=np.float32)
    for cue in plan.sfx:
        rng = np.random.default_rng(synth.seed_of(f"{plan.episode_slug}:{cue.id}:{cue.start_s}"))
        clip = synth.sfx(cue.family, rng, variant=cue.id)
        rms = float(np.sqrt(np.mean(clip ** 2))) or 1.0
        clip = clip * (speech_rms * 10 ** (SFX_VS_VOICE_DB / 20) / rms)
        clip = np.clip(clip, -0.6, 0.6)
        s = int(round(cue.start_s * synth.SR))
        if s < n:
            e = min(n, s + clip.size)
            sfx[s:e] += clip[: e - s]
    return music, sfx
