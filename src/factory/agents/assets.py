"""`assets` stage (M2): draw the visual plan's new props as SVG and store them in the library.

Per request: reuse a library asset with the same normalised name, else ask the model for an
SVG in the house style, sanitise it (allowlist, no text/scripts/links, palette, ink outline)
and retry with the problems as feedback (max 3 attempts). Every stored asset carries
provenance (generator, prompt hash, licence, source episode). Free-first: the SVG is drawn by
the subscription LLM, no image API (DECISIONS D2, D8).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from factory import resources
from factory.agents.common import load_upstream, save
from factory.assetlib import AssetLibrary, palette, sanitize_svg
from factory.db.models import Lane
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.providers.llm import LLMProvider, LLMRequest, Tier
from factory.schemas.visual import AssetManifest, SvgDraft, VisualPlan

PROMPT = "assets/v1"
MAX_ATTEMPTS = 3


def palette_hex() -> str:
    return ", ".join(f"#{r:02X}{g:02X}{b:02X}" for r, g, b in sorted(palette()))


class AssetsStage(Stage):
    name = "assets"
    lane = Lane.LLM
    version = "1"
    depends_on = ("visual_plan",)
    max_attempts = 2

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        return {"visual_plan": ctx.upstream["visual_plan"]["sha256"],
                "prompt": resources.sha256_text(resources.prompt(PROMPT)),
                "model": ctx.settings.llm_model_medium}

    def run(self, ctx: StageContext) -> StageResult:
        plan = load_upstream(ctx, "visual_plan", VisualPlan)
        lib = AssetLibrary(Path(ctx.settings.library_dir))
        manifest = AssetManifest(episode_slug=plan.episode_slug)
        for req in plan.asset_requests:
            existing = lib.find(req.name)
            if existing:
                manifest.resolved[req.request_id] = existing.asset_id
                manifest.reused.append(req.request_id)
                continue
            feedback = ""
            for attempt in range(1, MAX_ATTEMPTS + 1):
                prompt = resources.render(resources.prompt(PROMPT), name=req.name,
                                          description=req.description, palette=palette_hex(),
                                          feedback=feedback)
                draft = self._call(prompt, ctx)
                svg, problems = sanitize_svg(draft.svg)
                manifest.attempts[req.request_id] = attempt
                if not problems:
                    rec = lib.add(req.name, req.tags, svg,
                                  generator=f"{ctx.settings.llm_provider}:"
                                            f"{ctx.settings.llm_model_medium}",
                                  prompt=prompt, episode=plan.episode_slug)
                    manifest.resolved[req.request_id] = rec.asset_id
                    manifest.generated.append(req.request_id)
                    break
                feedback = ("\nYour previous SVG was rejected. Fix these problems:\n"
                            + "\n".join(f"- {p}" for p in problems) + "\n")
            else:
                raise PermanentStageError(
                    f"asset {req.request_id} ({req.name}) failed the style checks "
                    f"{MAX_ATTEMPTS} times; last problems: {feedback.strip()[:300]} "
                    f"(flag for human review or drop the prop from the visual plan)")
        ref = save(ctx, "assets", manifest)
        return StageResult({**ref, "generated": len(manifest.generated),
                            "reused": len(manifest.reused)})

    def _call(self, prompt: str, ctx: StageContext) -> SvgDraft:
        resp = self.llm.complete(
            LLMRequest(prompt=prompt, system="You draw clean, simple SVG illustrations.",
                       schema=SvgDraft, tier=Tier.MEDIUM, agent="assets"),
            record_usage=ctx.record_usage,
        )
        assert resp.data is not None
        return resp.data
