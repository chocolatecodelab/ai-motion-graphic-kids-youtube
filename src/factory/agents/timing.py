"""`timing` stage: storyboard + real voice durations -> frame-accurate render plan.

- Lines are laid out on each scene's clock with a lead-in, gaps and a tail; a scene is
  never shorter than its dialogue (it may be longer than the storyboard asked).
- Shots cut a few frames before the line they start on.
- Waypoints are timed to their lines; graphics appear on their trigger line.
- Mouth curves come from each line's audio loudness per frame (puppet lip-flap).
- Transitions: scene N's `transition_out` covers its last frames and reveals scene N+1.
- Subtitles from the vo_preview timeline are shifted onto the final episode timeline.
- Audio plan (v3): storyboard SFX land just before their trigger line, portal/whip/zoom
  transitions get their own whoosh, and each scene gets a music mood from its beat.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from factory.agents.common import content_dir, load_upstream, save
from factory.agents.subtitles import timed_words, to_srt, to_vtt
from factory.artifacts import write_text
from factory.captions import chunk_line
from factory.db.models import Lane
from factory.media import audio as A
from factory.media.synth import BEAT_MOOD, sfx_family
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.schemas.renderplan import (
    AudioCue,
    MusicSection,
    PlanBlocking,
    PlanCaption,
    PlanGraphic,
    PlanLine,
    PlanProp,
    PlanScene,
    PlanShot,
    PlanTransition,
    PlanWaypoint,
    PlanWord,
    RenderPlan,
    SfxCue,
)
from factory.schemas.script import Script
from factory.schemas.storyboard import Storyboard, StoryboardScene
from factory.schemas.visual import AssetManifest, VisualPlan
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
    ("underwater", ("underwater", "under the sea", "seabed", "seafloor", "coral", "reef")),
    ("workbench", ("workbench", "bench", "tools")),
    ("attic", ("attic", "shelf", "shelves", "boxes")),
    ("lab", ("laboratory", "lab bench", "beaker", "microscope", "test tube")),
    ("library", ("library", "bookshelf", "bookshelves")),
    ("cave", ("cave", "cavern", "stalactite", "crystal")),
    ("volcano", ("volcano", "lava", "magma")),
    ("arctic", ("arctic", "antarctic", "polar", "igloo", "glacier", "snowfield")),
    ("night", ("campfire", "campsite", "moonlit", "night sky")),
    ("sunset", ("sunset", "sunrise", "dusk", "evening sky")),
    ("air", ("molecule", "air", "dots", "haze", "particles")),
    ("sunbeam", ("sunbeam", "beam", "rainbow", "ribbon", "spectrum", "light corridor")),
    ("space", ("space", "stars", "planet", "orbit")),
    ("jungle", ("jungle", "rainforest", "vines")),
    ("forest", ("forest", "woods", "woodland")),
    ("desert", ("desert", "dune", "cactus")),
    ("ocean", ("ocean", "beach", "seaside", "shore", "waves")),
    ("mountains", ("mountain", "summit", "cliff")),
    ("city", ("city", "street", "town", "skyline")),
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
                tout: PlanTransition, cdir: Path,
                emotions: dict[str, str] | None = None) -> tuple[PlanScene, dict[str, int]]:
    emotions = emotions or {}
    t = max(LEAD_IN_S, tin.frames / FPS + 0.15)
    lines: list[PlanLine] = []
    captions: list[PlanCaption] = []
    starts: dict[str, int] = {}
    for lid in scene.line_ids:
        v = voice.get(lid)
        if v is None:
            raise PermanentStageError(f"no voice for {lid}")
        start = _frames(t * FPS)
        frames = max(1, _frames(v.duration_s * FPS))
        lines.append(PlanLine(line_id=lid, speaker=v.speaker, text=v.text,
                              emotion=emotions.get(lid, "neutral"),
                              start_frame=start, end_frame=start + frames,
                              mouth=mouth_curve(cdir / v.file, frames)))
        words = []
        for text, a, b in timed_words(v):  # script words, preview-timeline seconds
            s0 = start + _frames((a - v.preview_start_s) * FPS)
            s1 = start + _frames((b - v.preview_start_s) * FPS)
            s0 = min(max(s0, start), start + frames - 1)
            words.append(PlanWord(text=text, start_frame=s0,
                                  end_frame=min(max(s1, s0 + 1), start + frames)))
        captions += chunk_line(v.speaker, words)
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
        shots=shots, graphics=graphics, lines=lines, captions=captions,
        transition_in=tin, transition_out=tout)
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


def scene_props(ctx: StageContext) -> dict[str, list[PlanProp]]:
    """Visual plan placements -> render-plan props (library SVG inlined, already sanitised)."""
    from factory.assetlib import AssetLibrary

    plan = load_upstream(ctx, "visual_plan", VisualPlan)
    manifest = load_upstream(ctx, "assets", AssetManifest)
    lib = AssetLibrary(Path(ctx.settings.library_dir))
    out: dict[str, list[PlanProp]] = {}
    for s in plan.scenes:
        items = []
        for p in s.props:
            kind, _, ref = p.ref.partition(":")
            common = {"x": p.x, "y": p.y, "scale": p.scale, "depth": p.depth, "flip": p.flip}
            if kind == "builtin":
                items.append(PlanProp(kind="builtin", ref=ref, **common))
                continue
            asset_id = manifest.resolved.get(ref) if kind == "new" else ref
            if not asset_id:
                raise PermanentStageError(f"{s.scene_id}: prop {p.ref} has no asset; re-run assets")
            items.append(PlanProp(kind="svg", ref=asset_id, svg=lib.svg(asset_id), **common))
        out[s.scene_id] = items
    return out


SFX_LEAD_S = 0.08
TRANSITION_SFX = {"compass_portal": ("portal", 0.6), "whip": ("whoosh", 0.3),
                  "zoom_through": ("riser", 0.5), "wipe": ("whoosh", 0.3)}


def audio_plan(board: Storyboard, scenes: list[PlanScene], scene_starts: list[int],
               line_starts: dict[str, int]) -> tuple[list[SfxCue], list[MusicSection]]:
    sfx: list[SfxCue] = []
    music: list[MusicSection] = []
    for i, (scene, plan, s0) in enumerate(zip(board.scenes, scenes, scene_starts, strict=True)):
        for fx in scene.sfx:
            f = line_starts.get(fx.at_line) if fx.at_line else None
            t = f / FPS - SFX_LEAD_S if f is not None else s0 / FPS + 0.3
            sfx.append(SfxCue(id=fx.id, family=sfx_family(fx.id), scene_id=scene.scene_id,
                              start_s=round(max(0.0, t), 3)))
        tout = plan.transition_out
        if i < len(scenes) - 1 and tout.type in TRANSITION_SFX:
            family, lead = TRANSITION_SFX[tout.type]
            t = (s0 + plan.duration_frames - tout.frames) / FPS - lead
            sfx.append(SfxCue(id=f"transition_{tout.type}", family=family,
                              scene_id=scene.scene_id, start_s=round(max(0.0, t), 3)))
        mood = BEAT_MOOD.get(scene.beat, "curious")
        music.append(MusicSection(scene_id=scene.scene_id, mood=mood,
                                  start_s=round(s0 / FPS, 3),
                                  end_s=round((s0 + plan.duration_frames) / FPS, 3)))
    return sorted(sfx, key=lambda c: c.start_s), music


class TimingStage(Stage):
    name = "timing"
    lane = Lane.MEDIA
    version = "5"  # v5: line emotions from the script; v4: props; v3: SFX + music
    depends_on = ("script", "storyboard", "voice", "subtitles", "visual_plan", "assets")
    max_attempts = 1

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        return {k: ctx.upstream[k]["sha256"]
                for k in ("script", "storyboard", "voice", "subtitles", "visual_plan", "assets")}

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
        script = load_upstream(ctx, "script", Script)
        emotions = {ln.line_id: ln.emotion for ln in script.lines}

        scenes, starts_all, scene_starts = [], {}, []
        offset = 0
        for scene, (tin, tout) in zip(board.scenes, transitions(board), strict=True):
            plan, starts = build_scene(scene, voice, tin, tout, cdir, emotions)
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

        sfx, music = audio_plan(board, scenes, scene_starts, starts_all)
        props = scene_props(ctx)
        for sc in scenes:
            sc.props = props.get(sc.scene_id, [])
        plan = RenderPlan(episode_slug=board.episode_slug,
                          storyboard_version=int(ctx.upstream["storyboard"]["version"]),
                          fps=FPS, width=board.width, height=board.height, scenes=scenes,
                          scene_start_frames=scene_starts, total_frames=offset, audio=audio,
                          sfx=sfx, music=music,
                          subtitles_srt=srt, subtitles_vtt=vtt)
        longer = [f"{s.scene_id} extended to {p.duration_frames / FPS:.1f}s for its dialogue"
                  for s, p in zip(board.scenes, scenes, strict=True)
                  if p.duration_frames / FPS > s.duration_s + 0.5]
        plan.notes = longer
        ref = save(ctx, "renderplan", plan)
        return StageResult({**ref, "total_frames": offset, "total_s": round(offset / FPS, 2),
                            "srt": srt, "vtt": vtt, "scenes": len(scenes)})
