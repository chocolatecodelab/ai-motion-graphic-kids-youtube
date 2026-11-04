"""QA report artifact."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QACheck(BaseModel):
    id: str
    category: str
    status: Literal["pass", "fail", "warn"]
    severity: Literal["critical", "warning", "info"]
    detail: str
    fix_stage: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class QAReport(BaseModel):
    schema_version: Literal["qa.v1"] = "qa.v1"
    episode_slug: str
    video: str
    quality: str
    score: int
    verdict: Literal["pass", "fail"]
    critical: list[str]
    warnings: list[str]
    per_category: dict[str, int]
    fix_stages: list[str]
    checks: list[QACheck]
    disclaimer: str = (
        "Automated checks reduce risk but do not guarantee accuracy. M1 runs technical, speech, "
        "subtitle, content-reference and rights checks; AI visual and content review arrive in "
        "M3. A human approves the final video before publication."
    )
