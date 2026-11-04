"""`brief` stage (M1): load and validate the hand-written topic brief.

Replaced by research -> topic_select -> fact_check in M3; downstream stages
only depend on the `brief.v1` artifact, so they won't change.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml
from pydantic import ValidationError

from factory.agents.common import episode_dir, save
from factory.db.models import Lane
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.resources import sha256_text
from factory.schemas.brief import TopicBrief

INPUT_FILE = "inputs/brief.yaml"


class BriefStage(Stage):
    name = "brief"
    lane = Lane.LLM
    version = "1"
    max_attempts = 1

    def _source(self, ctx: StageContext):  # type: ignore[no-untyped-def]
        return episode_dir(ctx) / INPUT_FILE

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        path = self._source(ctx)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return {"brief_sha256": sha256_text(text)}

    def run(self, ctx: StageContext) -> StageResult:
        path = self._source(ctx)
        if not path.exists():
            raise PermanentStageError(f"brief not found: {path}")
        try:
            brief = TopicBrief.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (ValidationError, yaml.YAMLError) as exc:
            raise PermanentStageError(f"invalid brief: {exc}") from exc

        problems = []
        usable = brief.usable_claims()
        if len(usable) < 3:
            problems.append("fewer than 3 usable claims")
        sources = {s.id: s for s in brief.sources}
        for c in usable:
            tier1 = {e.source_id for e in c.evidence if sources[e.source_id].tier == 1}
            if not tier1:
                problems.append(f"{c.id} has no tier-1 source")
            if len({e.source_id for e in c.evidence}) < 2 and not c.is_twist:
                problems.append(f"{c.id} has fewer than 2 independent sources")
        if problems:
            raise PermanentStageError("brief fails source rules: " + "; ".join(problems))

        ref = save(ctx, "brief", brief)
        return StageResult({**ref, "claims": len(usable), "slug": brief.slug})
