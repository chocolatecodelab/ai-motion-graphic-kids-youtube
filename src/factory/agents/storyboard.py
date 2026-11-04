"""`storyboard` stage: approved script -> storyboard.v1 JSON for the renderer.

Code validation: same scenes/beats as the script, every line exactly once and in
order, rig IDs and component names from the catalogues, scene durations cover
their dialogue, total within target ±10%. Failures go back to the model (max 2).
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
from factory.schemas.storyboard import Storyboard, StoryboardDraft
from factory.storyboard_html import render_storyboard_html
from factory.text import LINE_GAP_S

PROMPT = "storyboard/v1"
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
        speakers = {by_line[lid].speaker for lid in s.line_ids if lid in by_line}
        on_screen = {c.character for c in s.characters}
        if not speakers <= on_screen:
            issues.append(f"{s.scene_id}: speakers {sorted(speakers)} must be in `characters`.")
        for c in s.characters:
            if c.pose not in rig.ids(c.character, "poses"):
                issues.append(f"{s.scene_id}: unknown pose {c.pose!r} for {c.character}.")
            if c.expression not in rig.ids(c.character, "expressions"):
                issues.append(f"{s.scene_id}: unknown expression {c.expression!r} "
                              f"for {c.character}.")
            if c.action and c.action not in rig.ids(c.character, "actions"):
                issues.append(f"{s.scene_id}: unknown action {c.action!r} for {c.character}.")
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

    total = sum(s.duration_s for s in draft.scenes)
    lo = brief.duration.min_s * (1 - TOLERANCE)
    hi = brief.duration.max_s * (1 + TOLERANCE)
    if not lo <= total <= hi:
        issues.append(f"Total duration {total:.1f}s is outside {lo:.0f}-{hi:.0f}s.")
    return issues


class StoryboardStage(Stage):
    name = "storyboard"
    lane = Lane.LLM
    version = "2"  # v2: numbers in graphics must cite a claim or be illustrative
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
