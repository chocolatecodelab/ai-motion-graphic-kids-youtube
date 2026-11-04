"""`script_validate` stage: independent safety/accuracy review, then the owner's approval.

A different model tier from the writer reviews the script (an LLM never grades
its own output in the same call). Code decides the verdict: any critical issue,
any unsupported factual statement, or any score below 3 fails the stage.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factory import resources
from factory.agents.common import (
    claims_block,
    content_dir,
    latest_feedback,
    load_upstream,
    save,
    write_feedback,
)
from factory.artifacts import write_text
from factory.config import PublicationMode
from factory.db.models import Lane
from factory.pipeline import (
    PermanentStageError,
    RevisionRequested,
    Stage,
    StageContext,
    StageResult,
)
from factory.providers.llm import LLMProvider, LLMRequest, Tier
from factory.schemas.brief import TopicBrief
from factory.schemas.review import ScriptReview, ScriptReviewDraft
from factory.schemas.script import Script

PROMPT = "script_validate/v1"
MIN_SCORE = 3
MAX_AUTO_REVISIONS = 2


def script_lines_block(script: Script) -> str:
    return "\n".join(
        f"{ln.line_id} [{ln.speaker}] {ln.text}"
        + (f"  (claims: {', '.join(ln.claim_ids)})" if ln.claim_ids else "")
        for ln in script.lines
    )


def verdict(draft: ScriptReviewDraft, script: Script) -> ScriptReview:
    """Code decides. Blocking: critical issues, critical/major unsupported facts, any score
    below MIN_SCORE. Minor unsupported statements (everyday knowledge, exclamations that
    restate a claim) become warnings the owner sees before approving."""
    reasons = [f"critical {i.category}: {i.detail}"
               for i in draft.issues if i.severity == "critical"]
    reasons += [f"unsupported {u.severity} statement in {u.line_id}: {u.text}"
                for u in draft.unsupported_statements if u.severity != "minor"]
    warnings = [f"minor unsupported statement in {u.line_id}: {u.text} ({u.reason})"
                for u in draft.unsupported_statements if u.severity == "minor"]
    warnings += [f"major {i.category}{f' ({i.line_id})' if i.line_id else ''}: {i.detail}"
                 for i in draft.issues if i.severity == "major"]
    scores = draft.scores.model_dump()
    low = {k: v for k, v in scores.items() if v < MIN_SCORE}
    reasons += [f"score {k}={v} is below {MIN_SCORE}" for k, v in low.items()]
    return ScriptReview(script_version=script.version, review=draft,
                        verdict="fail" if reasons else "pass", blocking_reasons=reasons,
                        warnings=warnings, min_score=min(scores.values()))


def feedback_text(review: ScriptReview) -> str:
    """Actionable feedback for the writer: blocking items first, then major issues."""
    r = review.review
    out = ["## Must fix (blocking)"]
    for u in r.unsupported_statements:
        if u.severity != "minor":
            out.append(f"- {u.line_id}: \"{u.text}\" is not covered by the verified claims "
                       f"({u.reason}). Reword it within the claims or cut it.")
    for i in r.issues:
        if i.severity == "critical":
            out.append(f"- {i.line_id or 'general'} ({i.category}): {i.detail} "
                       f"Suggestion: {i.suggestion}")
    low = [k for k, v in r.scores.model_dump().items() if v < MIN_SCORE]
    if low:
        out.append(f"- Raise these weak dimensions: {', '.join(low)}.")
    majors = [i for i in r.issues if i.severity == "major"]
    if majors:
        out.append("\n## Should fix")
        out += [f"- {i.line_id or 'general'} ({i.category}): {i.detail} Suggestion: "
                f"{i.suggestion}" for i in majors]
    return "\n".join(out) + "\n"


def markdown(review: ScriptReview) -> str:
    r = review.review
    out = [f"# Script review: {review.verdict.upper()}", "", r.summary, "", "## Scores"]
    out += [f"- {k}: {v}/5" for k, v in r.scores.model_dump().items()]
    if review.blocking_reasons:
        out += ["", "## Blocking", *[f"- {b}" for b in review.blocking_reasons]]
    if review.warnings:
        out += ["", "## Check before approving", *[f"- {w}" for w in review.warnings]]
    if r.issues:
        out += ["", "## Issues"]
        out += [f"- **{i.severity}** {i.category}{f' ({i.line_id})' if i.line_id else ''}: "
                f"{i.detail}{f' → {i.suggestion}' if i.suggestion else ''}" for i in r.issues]
    return "\n".join(out) + "\n"


class ScriptValidateStage(Stage):
    name = "script_validate"
    lane = Lane.LLM
    # v2: severity on unsupported statements (minor = warning). v3: auto-revision loop.
    version = "3"
    depends_on = ("brief", "script")
    max_attempts = 2
    # The owner approves the script before visuals start (WORKFLOW_SPECIFICATION stage 5).
    approval_modes = frozenset({PublicationMode.MANUAL, PublicationMode.APPROVAL_REQUIRED})

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
        prompt = resources.render(resources.prompt(PROMPT), claims=claims_block(brief),
                                  script_lines=script_lines_block(script))
        resp = self.llm.complete(
            LLMRequest(prompt=prompt, system=resources.shared_context(),
                       schema=ScriptReviewDraft, tier=Tier.MEDIUM, agent="script_validate"),
            record_usage=ctx.record_usage,
        )
        assert resp.data is not None
        review = verdict(resp.data, script)
        ref = save(ctx, "review", review)
        md = write_text(content_dir(ctx), ctx.workdir / f"review.v{ref['version']}.md",
                        markdown(review))
        if review.verdict == "fail":
            summary = " | ".join(review.blocking_reasons[:5])
            safety_critical = [i for i in review.review.issues if i.severity == "critical"
                               and i.category in ("safety", "privacy")]
            done, _ = latest_feedback(ctx, "script")
            if safety_critical or done >= MAX_AUTO_REVISIONS:
                why = ("safety-critical findings need a human" if safety_critical
                       else f"still failing after {done} automatic revisions")
                raise PermanentStageError(f"script review failed ({why}): {summary} "
                                          f"(full report: {md})")
            n = write_feedback(ctx, "script", feedback_text(review))
            raise RevisionRequested("script", f"review failed, requesting script revision "
                                              f"{n}/{MAX_AUTO_REVISIONS}: {summary}")
        return StageResult({**ref, "markdown": md, "verdict": review.verdict,
                            "min_score": review.min_score,
                            "issues": len(review.review.issues),
                            "warnings": len(review.warnings)})
