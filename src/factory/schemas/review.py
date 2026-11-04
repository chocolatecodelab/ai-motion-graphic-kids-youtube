"""Script safety / quality review (script_validate stage)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor"]


class ReviewIssue(BaseModel):
    severity: Severity
    category: Literal["safety", "age_appropriateness", "accuracy", "clarity", "tone",
                      "engagement", "privacy", "other"]
    line_id: str | None = Field(default=None, description="e.g. S03-L02, if specific")
    detail: str = Field(max_length=400)
    suggestion: str = Field(default="", max_length=400)


class UnsupportedStatement(BaseModel):
    line_id: str
    text: str = Field(max_length=400)
    reason: str = Field(max_length=300)
    severity: Severity = Field(
        description="critical/major: a substantive fact a kid could learn wrongly or that "
                    "needs a source. minor: everyday knowledge or a restatement/exclamation "
                    "directly implied by a verified claim."
    )


class ReviewScores(BaseModel):
    """1 (poor) to 5 (excellent)."""

    safety: int = Field(ge=1, le=5)
    age_appropriateness: int = Field(ge=1, le=5)
    accuracy: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    story: int = Field(ge=1, le=5)
    character_voice: int = Field(ge=1, le=5)


class ScriptReviewDraft(BaseModel):
    """LLM output."""

    scores: ReviewScores
    issues: list[ReviewIssue] = Field(default_factory=list)
    unsupported_statements: list[UnsupportedStatement] = Field(
        default_factory=list,
        description="Factual statements not covered by any verified claim",
    )
    summary: str = Field(max_length=800)


class ScriptReview(BaseModel):
    schema_version: Literal["review.v1"] = "review.v1"
    script_version: int
    review: ScriptReviewDraft
    verdict: Literal["pass", "fail"]
    blocking_reasons: list[str]
    warnings: list[str] = Field(default_factory=list)  # shown to the owner at approval
    min_score: int
