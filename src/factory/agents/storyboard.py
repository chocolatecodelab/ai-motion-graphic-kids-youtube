"""`storyboard` stage: approved script -> storyboard.v2 JSON for the renderer.

Code validation: same scenes/beats as the script, every line exactly once and in
order, rig IDs and component names from the catalogues, speakers on screen (or a
voice-over shot), scene durations cover their dialogue, total within target ±10%,
and the variety rules (shot sizes, angles, movement, no parked left/right pairs).
Failures go back to the model (max 2).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from factory import resources
from factory.agents.common import claims_block, content_dir, load_upstream, save
from factory.artifacts import write_text
from factory.db.models import Lane
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.providers.llm import LLMProvider, LLMRequest, Tier
from factory.schemas.brief import TopicBrief
from factory.schemas.script import Script
from factory.schemas.storyboard import (
    OFFSCREEN_OK_SHOTS,
    Shot,
    Storyboard,
    StoryboardDraft,
    StoryboardScene,
)
from factory.storyboard_html import render_storyboard_html
from factory.text import LINE_GAP_S

PROMPT = "storyboard/v2"
MAX_REVISIONS = 2
TOLERANCE = 0.10


def has_numbers(value: Any) -> bool:
    """True if any numeric value (not bool) appears anywhere in the props."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    if isinstance(value, dict):
        return any(has_numbers(v) for v in value.values())
    if isinstance(value, list | tuple):
        return any(has_numbers(v) for v in value)
    return False


def check_storyboard(draft: StoryboardDraft, script: Script, brief: TopicBrief) -> list[str]:
    issues: list[str] = []
    rig, comps = resources.rig(), resources.components()
    usable_claims = {c.id for c in brief.usable_claims()}
    script_scenes = [(s.key, s.beat) for s in script.draft.scenes]
    board_scenes = [(s.scene_id, s.beat) for s in draft.scenes]
    if board_scenes != script_scenes:
        issues.append(f"Scenes must match the script exactly: {script_scenes}; "
                      f"got {board_scenes}.")

    by_line = {ln.line_id: ln for ln in script.lines}
    used = [lid for s in draft.scenes for lid in s.line_ids]
    expected = [ln.line_id for ln in script.lines]
    if used != expected:
        missing = [lid for lid in expected if lid not in used]
        extra = [lid for lid in used if lid not in by_line]
        dupes = sorted({lid for lid in used if used.count(lid) > 1})
        issues.append(f"Every script line must appear exactly once, in order. "
                      f"Missing {missing}, unknown {extra}, duplicated {dupes}.")

    for s in draft.scenes:
        for lid in s.line_ids:
            if lid in by_line and by_line[lid].scene_key != s.scene_id:
                issues.append(f"{lid} belongs to {by_line[lid].scene_key}, not {s.scene_id}.")
        speech = sum(by_line[lid].est_duration_s + LINE_GAP_S
                     for lid in s.line_ids if lid in by_line)
        if s.duration_s + 1e-6 < speech:
            issues.append(f"{s.scene_id} lasts {s.duration_s}s but its lines need "
                          f"{speech:.1f}s.")
        issues += check_shots(s, by_line, rig)
        for mg in s.motion_graphics:
            if mg.component not in comps.items:
                issues.append(f"{s.scene_id}: unknown component {mg.component!r}.")
            unknown_claims = [c for c in mg.claim_ids if c not in usable_claims]
            if unknown_claims:
                issues.append(f"{s.scene_id}: {mg.component} cites unknown claims "
                              f"{unknown_claims}.")
            if has_numbers(mg.props) and not mg.illustrative and not mg.claim_ids:
                issues.append(f"{s.scene_id}: {mg.component} shows numbers "
                              f"({json.dumps(mg.props)[:120]}) that no verified claim states. "
                              f"Set illustrative=true (renderer hides the numbers) or cite "
                              f"the claim_ids that state them.")
            if mg.at_line and mg.at_line not in s.line_ids:
                issues.append(f"{s.scene_id}: motion graphic at_line {mg.at_line} "
                              f"is not a line of this scene.")
        for fx in s.sfx:
            if fx.at_line and fx.at_line not in s.line_ids:
                issues.append(f"{s.scene_id}: sfx at_line {fx.at_line} is not in this scene.")
        if not (s.background.library_id or s.background.asset_request):
            issues.append(f"{s.scene_id}: background needs a library_id or asset_request.")
        if s.background.theme is None:
            issues.append(f"{s.scene_id}: background.theme is required (pick the closest "
                          f"environment from the list).")

    total = sum(s.duration_s for s in draft.scenes)
    lo = brief.duration.min_s * (1 - TOLERANCE)
    hi = brief.duration.max_s * (1 + TOLERANCE)
    if not lo <= total <= hi:
        issues.append(f"Total duration {total:.1f}s is outside {lo:.0f}-{hi:.0f}s.")
    issues += check_variety(draft)
    return issues


def shot_spans(scene: StoryboardScene) -> list[tuple[Shot, list[str]]]:
    """Each shot with the line IDs spoken during it."""
    starts = [scene.line_ids.index(sh.starts_at_line) if sh.starts_at_line in scene.line_ids
              else 0 for sh in scene.shots]
    spans = []
    for i, sh in enumerate(scene.shots):
        end = starts[i + 1] if i + 1 < len(starts) else len(scene.line_ids)
        spans.append((sh, scene.line_ids[starts[i]:end]))
    return spans


def check_shots(s: StoryboardScene, by_line: dict, rig: resources.Rig) -> list[str]:  # type: ignore[type-arg]
    issues: list[str] = []
    prev_start = -1
    for i, sh in enumerate(s.shots):
        if i == 0 and sh.starts_at_line not in (None, s.line_ids[0] if s.line_ids else None):
            issues.append(f"{s.scene_id}: the first shot must start at the scene start "
                          f"(starts_at_line null).")
        if i > 0:
            if sh.starts_at_line not in s.line_ids:
                issues.append(f"{s.scene_id} shot {i + 1}: starts_at_line must be a line of "
                              f"this scene.")
            else:
                idx = s.line_ids.index(sh.starts_at_line)
                if idx <= prev_start:
                    issues.append(f"{s.scene_id}: shots must start at increasing lines.")
                prev_start = idx
        else:
            prev_start = 0
        for b in sh.blocking:
            where = f"{s.scene_id} shot {i + 1} {b.character}"
            if b.pose not in rig.ids(b.character, "poses"):
                issues.append(f"{where}: unknown pose {b.pose!r}.")
            if b.expression not in rig.ids(b.character, "expressions"):
                issues.append(f"{where}: unknown expression {b.expression!r}.")
            if b.action and b.action not in rig.ids(b.character, "actions"):
                issues.append(f"{where}: unknown action {b.action!r}.")
            for wp in b.path:
                if wp.at_line and wp.at_line not in s.line_ids:
                    issues.append(f"{where}: path at_line {wp.at_line} is not in this scene.")
        if len({b.character for b in sh.blocking}) != len(sh.blocking):
            issues.append(f"{s.scene_id} shot {i + 1}: a character appears twice.")
    for sh, lines in shot_spans(s):
        if sh.shot_type in OFFSCREEN_OK_SHOTS or sh.focus in ("graphic", "background"):
            continue
        speakers = {by_line[lid].speaker for lid in lines if lid in by_line}
        on_screen = {b.character for b in sh.blocking}
        missing = speakers - on_screen
        if missing:
            issues.append(f"{s.scene_id}: {sorted(missing)} speaks during a {sh.shot_type} "
                          f"shot but is not in its blocking (use an insert/pov shot or focus "
                          f"'graphic' for voice-over).")
    return issues


def _moves(sh: Shot) -> bool:
    return sh.camera_move != "static" or any(
        b.motion != "none" or b.path or b.enter != "none" or b.exit != "none"
        for b in sh.blocking)


def check_variety(draft: StoryboardDraft) -> list[str]:
    """Adventure-style staging: owner direction (DECISIONS.md 2026-11-04)."""
    issues: list[str] = []
    shots = [(s.scene_id, sh) for s in draft.scenes for sh in s.shots]
    for i in range(2, len(shots)):
        trio = [sh for _, sh in shots[i - 2:i + 1]]
        if len({sh.shot_type for sh in trio}) == 1:
            issues.append(f"Three shots in a row are {trio[0].shot_type} "
                          f"({', '.join(sid for sid, _ in shots[i - 2:i + 1])}). Vary the "
                          f"shot sizes.")
    if len({sh.shot_type for _, sh in shots}) < 4:
        issues.append("Use at least 4 different shot types across the episode.")
    if len({sh.angle for _, sh in shots}) < 3:
        issues.append("Use at least 3 different camera angles across the episode.")
    moving = sum(_moves(sh) for _, sh in shots)
    if moving < len(shots) * 0.6:
        issues.append(f"Only {moving}/{len(shots)} shots have camera or character movement; "
                      f"make at least 60% move.")
    for s in draft.scenes:
        if s.beat == "adventure" and not any(_moves(sh) for sh in s.shots):
            issues.append(f"{s.scene_id} is an adventure scene with no movement.")
    parked = 0
    for _, sh in shots:  # Arka left + Lipa right, again and again
        pos = {b.character: b.x for b in sh.blocking}
        if pos.get("arka", 0.5) < 0.38 and pos.get("lipa", 0.5) > 0.62:
            parked += 1
    if parked > len(shots) * 0.4:
        issues.append(f"Arka is parked left and Lipa right in {parked}/{len(shots)} shots; "
                      f"vary their positions, depth and scale.")
    return issues


class StoryboardStage(Stage):
    name = "storyboard"
    lane = Lane.LLM
    version = "4"  # v3: storyboard.v2 shots/blocking + variety rules; v4: explicit theme
    depends_on = ("brief", "script", "script_validate")
    max_attempts = 2

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        return {"brief": ctx.upstream["brief"]["sha256"],
                "script": ctx.upstream["script"]["sha256"],
                "resources": resources.resource_hash(PROMPT),
                "model": ctx.settings.llm_model_medium}

    def run(self, ctx: StageContext) -> StageResult:
        brief = load_upstream(ctx, "brief", TopicBrief)
        script = load_upstream(ctx, "script", Script)
        rig, comps = resources.rig(), resources.components()
        lines = "\n".join(f"{ln.line_id} [{ln.speaker}, ~{ln.est_duration_s}s] {ln.text}"
                          for ln in script.lines)
        scenes = "\n".join(f"{s.key} ({s.beat}) at {s.location}: {s.summary} | visuals: "
                           f"{'; '.join(s.visual_opportunities) or '-'}"
                           for s in script.draft.scenes)
        prompt = resources.render(resources.prompt(PROMPT), script_lines=lines,
                                  scene_summaries=scenes, rig=rig.describe(),
                                  components=comps.describe(), claims=claims_block(brief),
                                  min_s=brief.duration.min_s, max_s=brief.duration.max_s)
        draft = self._call(prompt, ctx)
        issues = check_storyboard(draft, script, brief)
        revisions = 0
        while issues and revisions < MAX_REVISIONS:
            revisions += 1
            fix = ("\n\nYour previous storyboard failed these checks. Return a corrected full "
                   "storyboard.\n" + "\n".join(f"- {i}" for i in issues)
                   + "\n\nPrevious storyboard (JSON):\n"
                   + json.dumps(draft.model_dump(), ensure_ascii=False))
            draft = self._call(prompt + fix, ctx)
            issues = check_storyboard(draft, script, brief)
        if issues:
            raise PermanentStageError(
                f"storyboard fails {len(issues)} check(s) after {revisions} revisions: "
                + " | ".join(issues[:5])
            )
        board = Storyboard(episode_slug=script.episode_slug, script_version=script.version,
                           scenes=draft.scenes,
                           total_duration_s=round(sum(s.duration_s for s in draft.scenes), 2),
                           catalogue_version=comps.version, rig_version=rig.version)
        ref = save(ctx, "storyboard", board)
        html_path = write_text(
            content_dir(ctx), ctx.workdir / f"storyboard.v{ref['version']}.html",
            render_storyboard_html(board, script, brief, ref["version"]),
        )
        return StageResult({**ref, "html": html_path, "scenes": len(board.scenes),
                            "total_duration_s": board.total_duration_s,
                            "revisions": revisions})

    def _call(self, prompt: str, ctx: StageContext) -> StoryboardDraft:
        resp = self.llm.complete(
            LLMRequest(prompt=prompt, system=resources.shared_context(),
                       schema=StoryboardDraft, tier=Tier.MEDIUM, agent="storyboard"),
            record_usage=ctx.record_usage,
        )
        assert resp.data is not None
        return resp.data
