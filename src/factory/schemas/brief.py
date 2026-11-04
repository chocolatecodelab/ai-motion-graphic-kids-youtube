"""Topic brief + verified claims: the input to scriptwriting.

In M1 the brief is written by hand (docs/PROJECT_PLAN.md: "topic and claims
provided manually"). From M3 the Research and Fact-Check agents produce it.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from factory.db.models import Pillar

ClaimStatus = Literal["supported", "partially_supported", "unsupported", "contradicted", "opinion"]


class Source(BaseModel):
    id: str = Field(pattern=r"^SRC\d{2}$")
    url: HttpUrl
    title: str
    publisher: str
    tier: Literal[1, 2, 3]  # 1 = primary institution / peer-reviewed
    retrieved_at: date


class Evidence(BaseModel):
    source_id: str
    quote: str = Field(min_length=8, max_length=200)


class Claim(BaseModel):
    id: str = Field(pattern=r"^C\d{2}$")
    text: str
    category: Literal["scientific", "historical", "numeric", "safety"]
    status: ClaimStatus
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(min_length=1)
    simplification_note: str | None = None
    is_twist: bool = False

    @property
    def usable(self) -> bool:
        """Only these claims may be referenced by the script."""
        return self.status in ("supported", "partially_supported")


class DurationTarget(BaseModel):
    min_s: int = Field(ge=30)
    max_s: int = Field(le=900)

    @model_validator(mode="after")
    def _order(self) -> DurationTarget:
        if self.min_s > self.max_s:
            raise ValueError("min_s must be <= max_s")
        return self


class TopicBrief(BaseModel):
    schema_version: Literal["brief.v1"] = "brief.v1"
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str
    central_question: str
    pillar: Pillar
    target_age_min: int = 8
    target_age_max: int = 12
    learning_objectives: list[str] = Field(min_length=1, max_length=4)
    storytelling_angle: str
    twist: str | None = None
    duration: DurationTarget
    sources: list[Source] = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    verification: Literal["manual", "agent"] = "manual"
    notes: str | None = None

    @field_validator("central_question")
    @classmethod
    def _is_question(cls, v: str) -> str:
        if not v.strip().endswith("?"):
            raise ValueError("central_question must be a question")
        return v

    @model_validator(mode="after")
    def _references(self) -> TopicBrief:
        src_ids = {s.id for s in self.sources}
        if len(src_ids) != len(self.sources):
            raise ValueError("duplicate source ids")
        claim_ids = [c.id for c in self.claims]
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("duplicate claim ids")
        for c in self.claims:
            for e in c.evidence:
                if e.source_id not in src_ids:
                    raise ValueError(f"claim {c.id} cites unknown source {e.source_id}")
        return self

    def usable_claims(self) -> list[Claim]:
        return [c for c in self.claims if c.usable]


def normalize_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
