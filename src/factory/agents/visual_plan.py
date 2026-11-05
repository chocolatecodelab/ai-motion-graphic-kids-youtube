"""`visual_plan` stage (Visual Director, M2): set dressing per scene.

Places 1-4 props per scene from the built-in catalogue, the asset library, or new SVG prop
requests (drawn by the `assets` stage). Code validation: scenes match the storyboard, refs
exist, the centre stays clear for the characters, at most 4 new assets, every request used,
no requests for characters/text/brands. Failures go back to the model (max 2).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from factory import resources
from factory.agents.common import load_upstream, save
from factory.assetlib import AssetLibrary
from factory.db.models import Lane
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.providers.llm import LLMProvider, LLMRequest, Tier
from factory.schemas.storyboard import THEME_GUIDE, Storyboard
from factory.schemas.visual import VisualPlan, VisualPlanDraft

PROMPT = "visual_plan/v1"
MAX_REVISIONS = 2
EDGE_LO, EDGE_HI = 0.25, 0.75  # near/front props must stay outside this band
FORBIDDEN = re.compile(r"\b(text|letters?|words?|numbers?|logo|brand|arka|lipa|person|people|"
                       r"boy|girl|child|face|character)\b", re.I)


def check_visual_plan(draft: VisualPlanDraft, board: Storyboard,
                      library: AssetLibrary) -> list[str]:
    issues: list[str] = []
    builtin = set(resources.props().items)
    assets = {r.asset_id for r in library.records()}
    requests = {r.request_id for r in draft.asset_requests}
    want = [s.scene_id for s in board.scenes]
    got = [s.scene_id for s in draft.scenes]
    if got != want:
        issues.append(f"Return one entry per storyboard scene, in order: {want}; got {got}.")
    if len(requests) != len(draft.asset_requests):
        issues.append("asset_requests have duplicate request_id values.")
    used: set[str] = set()
    for s in draft.scenes:
        for p in s.props:
            kind, _, ref = p.ref.partition(":")
            if kind == "builtin" and ref not in builtin:
                issues.append(f"{s.scene_id}: unknown built-in prop {ref!r}.")
            elif kind == "asset" and ref not in assets:
                issues.append(f"{s.scene_id}: unknown library asset {ref!r}.")
            elif kind == "new":
                if ref not in requests:
                    issues.append(f"{s.scene_id}: new:{ref} has no matching asset_request.")
                used.add(ref)
            elif kind not in {"builtin", "asset", "new"}:
                issues.append(f"{s.scene_id}: ref {p.ref!r} must start with builtin:, asset: or "
                              f"new:.")
            if p.depth in {"near", "front"} and EDGE_LO < p.x < EDGE_HI:
                issues.append(f"{s.scene_id}: {p.ref} at x={p.x} ({p.depth}) would stand where "
                              f"the characters are; use x <= {EDGE_LO} or x >= {EDGE_HI}.")
    for r in draft.asset_requests:
        if r.request_id not in used:
            issues.append(f"asset_request {r.request_id} is never placed; place it or drop it.")
        bad = FORBIDDEN.findall(f"{r.name} {r.description}")
        if bad:
            issues.append(f"asset_request {r.request_id} mentions {sorted(set(bad))}: props must "
                          f"be plain objects (no characters, text or brands).")
    return issues


class VisualPlanStage(Stage):
    name = "visual_plan"
    lane = Lane.LLM
    version = "1"
    depends_on = ("storyboard",)
    max_attempts = 2

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def library(self, ctx: StageContext) -> AssetLibrary:
        return AssetLibrary(Path(ctx.settings.library_dir))

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        lib = self.library(ctx)
        return {"storyboard": ctx.upstream["storyboard"]["sha256"],
                "prompt": resources.sha256_text(resources.prompt(PROMPT)),
                "props": resources.props().version, "library": lib.index_sha256(),
                "model": ctx.settings.llm_model_medium}

    def run(self, ctx: StageContext) -> StageResult:
        board = load_upstream(ctx, "storyboard", Storyboard)
        lib = self.library(ctx)
        scenes = "\n".join(
            f"- {s.scene_id} ({s.beat}) theme={s.background.theme}: "
            f"{s.background.asset_request or s.background.library_id or ''} | goal: {s.objective}"
            f" | graphics: {', '.join(g.component for g in s.motion_graphics) or '-'}"
            for s in board.scenes)
        themes = "\n".join(f"- {k}: {v}" for k, v in THEME_GUIDE.items()
                           if k in {s.background.theme for s in board.scenes})
        prompt = resources.render(resources.prompt(PROMPT), scenes=scenes, themes=themes,
                                  builtin=resources.props().describe(), library=lib.describe())
        draft = self._call(prompt, ctx)
        issues = check_visual_plan(draft, board, lib)
        revisions = 0
        while issues and revisions < MAX_REVISIONS:
            revisions += 1
            fix = ("\n\nYour previous plan failed these checks. Return a corrected full plan.\n"
                   + "\n".join(f"- {i}" for i in issues)
                   + "\n\nPrevious plan (JSON):\n" + json.dumps(draft.model_dump()))
            draft = self._call(prompt + fix, ctx)
            issues = check_visual_plan(draft, board, lib)
        if issues:
            raise PermanentStageError(f"visual plan fails {len(issues)} check(s): "
                                      + " | ".join(issues[:5]))
        plan = VisualPlan(episode_slug=board.episode_slug,
                          storyboard_version=int(ctx.upstream["storyboard"]["version"]),
                          scenes=draft.scenes, asset_requests=draft.asset_requests,
                          prop_catalogue_version=resources.props().version)
        ref = save(ctx, "visual_plan", plan)
        return StageResult({**ref, "props": sum(len(s.props) for s in plan.scenes),
                            "asset_requests": len(plan.asset_requests), "revisions": revisions})

    def _call(self, prompt: str, ctx: StageContext) -> VisualPlanDraft:
        resp = self.llm.complete(
            LLMRequest(prompt=prompt, system=resources.shared_context(), schema=VisualPlanDraft,
                       tier=Tier.MEDIUM, agent="visual_plan"),
            record_usage=ctx.record_usage,
        )
        assert resp.data is not None
        return resp.data
