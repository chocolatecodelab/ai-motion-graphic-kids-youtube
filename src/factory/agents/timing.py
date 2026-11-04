"""`timing` stage: storyboard + real voice durations -> frame-accurate render plan.

- Lines are laid out on each scene's clock with a lead-in, gaps and a tail; a scene is
  never shorter than its dialogue (it may be longer than the storyboard asked).
- Shots cut a few frames before the line they start on.
- Waypoints are timed to their lines; graphics appear on their trigger line.
- Mouth curves come from each line's audio loudness per frame (puppet lip-flap).
- Transitions: scene N's `transition_out` covers its last frames and reveals scene N+1.
- Subtitles from the vo_preview timeline are shifted onto the final episode timeline.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from factory.agents.common import content_dir, load_upstream, save
from factory.agents.subtitles import to_srt, to_vtt
from factory.artifacts import write_text
from factory.db.models import Lane
from factory.media import audio as A
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.schemas.renderplan import (
    AudioCue,
    PlanBlocking,
    PlanGraphic,
    PlanLine,
    PlanScene,
    PlanShot,
    PlanTransition,
    PlanWaypoint,
    RenderPlan,
)
from factory.schemas.storyboard import Storyboard, StoryboardScene
from factory.schemas.voice import Cue, Subtitles, VoiceManifest

FPS = 30
LEAD_IN_S = 0.45
GAP_S = 0.25
TAIL_S = 0.6
CUT_LEAD_FRAMES = 4
FIRST_TRANSITION_FRAMES = 12

# Fallback only (the storyboard picks `background.theme` explicitly). Order matters:
# indoor places first, because attic descriptions often mention sunbeams or the sky.
THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("mars", ("mars", "martian")),
    ("workbench", ("workbench", "bench", "tools")),
    ("attic", ("attic", "shelf", "shelves", "boxes")),
    ("sunset", ("sunset", "sunrise", "dusk", "evening sky")),
    ("air", ("molecule", "air", "dots", "haze", "particles")),
    ("sunbeam", ("sunbeam", "beam", "rainbow", "ribbon", "spectrum", "light corridor")),
    ("space", ("space", "stars", "planet", "orbit")),
    ("sky", ("sky", "cloud", "hilltop", "rooftop", "outdoor")),
]


def theme_for(description: str) -> str:
    text = description.lower()
    for theme, words in THEME_KEYWORDS:
        if any(re.search(rf"\b{re.escape(w)}", text) for w in words):
            return theme
    return "studio"


def mouth_curve(path: Path, frames: int) -> list[float]:
    """Mouth openness 0..1 per video frame from the clip's loudness."""
    audio, sr = A.read_wav(path)
    hop = sr / FPS
    rms = np.array([
        A.rms(audio[int(i * hop):int((i + 1) * hop)]) for i in range(frames)
    ])
    if not rms.size or rms.max() <= 0:
        return [0.0] * frames
    ref = float(np.percentile(rms[rms > 0], 95)) if np.any(rms > 0) else 1.0
    level = np.clip(rms / max(ref, 1e-6), 0, 1)
    level[20 * np.log10(np.maximum(rms, 1e-9)) < -45] = 0.0
    out, prev = [], 0.0
    for v in level:  # fast attack, slower release: reads as speech, not flicker
        prev = v if v > prev else prev * 0.6 + v * 0.4
        out.append(round(float(prev), 2))
    return out


def _frames(value: float) -> int:
    return int(round(value))


def build_scene(scene: StoryboardScene, voice: dict[str, Any], tin: PlanTransition,
                tout: PlanTransition, cdir: Path) -> tuple[PlanScene, dict[str, int]]:
    t = max(LEAD_IN_S, tin.frames / FPS + 0.15)
    lines: list[PlanLine] = []
    starts: dict[str, int] = {}
    for lid in scene.line_ids:
        v = voice.get(lid)
        if v is None:
            raise PermanentStageError(f"no voice for {lid}")
        start = _frames(t * FPS)
        frames = max(1, _frames(v.duration_s * FPS))
        lines.append(PlanLine(line_id=lid, speaker=v.speaker, text=v.text, emotion="neutral",
                              start_frame=start, end_frame=start + frames,
                              mouth=mouth_curve(cdir / v.file, frames)))
        starts[lid] = start
        t += v.duration_s + GAP_S
    speech_end = t - GAP_S
    duration = _frames(max(scene.duration_s, speech_end + TAIL_S + tout.frames / FPS) * FPS)

    shot_starts = []
    for i, sh in enumerate(scene.shots):
        if i == 0 or sh.starts_at_line not in starts:
            shot_starts.append(0 if i == 0 else shot_starts[-1] + 1)
        else:
            cut = starts[sh.starts_at_line] - CUT_LEAD_FRAMES
            shot_starts.append(max(shot_starts[-1] + 1, cut))
    shots: list[PlanShot] = []
    for i, sh in enumerate(scene.shots):
        s0 = shot_starts[i]
        s1 = shot_starts[i + 1] if i + 1 < len(shot_starts) else duration
        length = max(1, s1 - s0)
        blocking = []
        for b in sh.blocking:
            path, last = [], 0
            for k, wp in enumerate(b.path):
                if wp.at_line and wp.at_line in starts:
                    f = starts[wp.at_line] - s0
                else:
                    f = round(length * (k + 1) / len(b.path)) - 1
                f = min(max(f, last + 1), length - 1)
                last = f
                path.append(PlanWaypoint(x=wp.x, y=wp.y, scale=wp.scale, frame=f))
            blocking.append(PlanBlocking(
                character=b.character, x=b.x, y=b.y, scale=b.scale, depth=b.depth,
                facing=b.facing, pose=b.pose, expression=b.expression, action=b.action,
                enter=b.enter, exit=b.exit, motion=b.motion, path=path))
        shots.append(PlanShot(start_frame=s0, end_frame=s1, shot_type=sh.shot_type,
                              angle=sh.angle, camera_move=sh.camera_move, focus=sh.focus,
                              blocking=blocking))

    graphics = []
    for mg in scene.motion_graphics:
        start = starts.get(mg.at_line, _frames(0.5 * FPS)) if mg.at_line else _frames(0.5 * FPS)
        graphics.append(PlanGraphic(component=mg.component, props=mg.props,
                                    illustrative=mg.illustrative, start_frame=start,
                                    end_frame=max(start + 1, duration - tout.frames)))

    plan = PlanScene(
        scene_id=scene.scene_id, beat=scene.beat, duration_frames=duration,
        theme=scene.background.theme or theme_for(
            scene.background.asset_request or scene.background.library_id or ""),
        background_description=scene.background.asset_request or "",
        shots=shots, graphics=graphics, lines=lines, transition_in=tin, transition_out=tout)
    return plan, starts


def transitions(board: Storyboard) -> list[tuple[PlanTransition, PlanTransition]]:
    out = []
    n = len(board.scenes)
    for i, s in enumerate(board.scenes):
        half = _frames(s.transition_out.duration_s * FPS / 2)
        out_t = (PlanTransition(type="fade", frames=FIRST_TRANSITION_FRAMES) if i == n - 1 else
                 PlanTransition(type=s.transition_out.type,
                                frames=0 if s.transition_out.type == "cut" else max(6, half)))
        if i == 0:
            in_t = PlanTransition(type="fade", frames=FIRST_TRANSITION_FRAMES)
        else:
            prev = board.scenes[i - 1].transition_out
            in_t = PlanTransition(type=prev.type, frames=0 if prev.type == "cut"
                                  else max(6, _frames(prev.duration_s * FPS / 2)))
        out.append((in_t, out_t))
    return out


class TimingStage(Stage):
    name = "timing"
    lane = Lane.MEDIA
    version = "1"
    depends_on = ("storyboard", "voice", "subtitles")
    max_attempts = 1

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        return {k: ctx.upstream[k]["sha256"] for k in ("storyboard", "voice", "subtitles")}

    def run(self, ctx: StageContext) -> StageResult:
        board = load_upstream(ctx, "storyboard", Storyboard)
        manifest = load_upstream(ctx, "voice", VoiceManifest)
        subs = load_upstream(ctx, "subtitles", Subtitles)
        if manifest.script_version != board.script_version:
            raise PermanentStageError(
                f"voice is for script v{manifest.script_version} but the storyboard is for "
                f"v{board.script_version}; re-run voice")
        cdir = content_dir(ctx)
        voice = {v.line_id: v for v in manifest.lines}

        scenes, starts_all, scene_starts = [], {}, []
        offset = 0
        for scene, (tin, tout) in zip(board.scenes, transitions(board), strict=True):
            plan, starts = build_scene(scene, voice, tin, tout, cdir)
            scenes.append(plan)
            scene_starts.append(offset)
            starts_all.update({lid: offset + f for lid, f in starts.items()})
            offset += plan.duration_frames

        audio = [AudioCue(line_id=v.line_id, file=v.file,
                          start_s=round(starts_all[v.line_id] / FPS, 3),
                          duration_s=v.duration_s) for v in manifest.lines]
        shift = {v.line_id: starts_all[v.line_id] / FPS - v.preview_start_s for v in manifest.lines}
        cues = [Cue(index=c.index, start=round(c.start + shift[c.line_id], 3),
                    end=round(c.end + shift[c.line_id], 3), speaker=c.speaker,
                    line_id=c.line_id, lines=c.lines) for c in subs.cues]
        for a, b in zip(cues, cues[1:], strict=False):
            if a.end > b.start:
                a.end = b.start
        srt = write_text(cdir, ctx.workdir / "en.srt", to_srt(cues))
        vtt = write_text(cdir, ctx.workdir / "en.vtt", to_vtt(cues))

        plan = RenderPlan(episode_slug=board.episode_slug,
                          storyboard_version=int(ctx.upstream["storyboard"]["version"]),
                          fps=FPS, width=board.width, height=board.height, scenes=scenes,
                          scene_start_frames=scene_starts, total_frames=offset, audio=audio,
                          subtitles_srt=srt, subtitles_vtt=vtt)
        longer = [f"{s.scene_id} extended to {p.duration_frames / FPS:.1f}s for its dialogue"
                  for s, p in zip(board.scenes, scenes, strict=True)
                  if p.duration_frames / FPS > s.duration_s + 0.5]
        plan.notes = longer
        ref = save(ctx, "renderplan", plan)
        return StageResult({**ref, "total_frames": offset, "total_s": round(offset / FPS, 2),
                            "srt": srt, "vtt": vtt, "scenes": len(scenes)})
