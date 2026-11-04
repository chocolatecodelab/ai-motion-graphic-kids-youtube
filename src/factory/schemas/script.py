"""Episode script: QUESTION -> ADVENTURE -> DISCOVERY in six beats."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Beat = Literal["hook", "mystery", "adventure", "discovery", "twist", "takeaway"]
BEAT_ORDER: tuple[Beat, ...] = ("hook", "mystery", "adventure", "discovery", "twist", "takeaway")
Speaker = Literal["kai", "needle"]
Emotion = Literal["neutral", "curious", "excited", "surprised", "puzzled", "determined",
                  "delighted", "playful", "thoughtful"]


class ScriptLine(BaseModel):
    speaker: Speaker
    text: str = Field(min_length=1, max_length=400)
    emotion: Emotion = "neutral"
    claim_ids: list[str] = Field(default_factory=list,
                                 description="IDs of verified claims this line states")
    direction: str = Field(default="", max_length=200,
                           description="Short acting/visual note, not spoken")


class ScriptScene(BaseModel):
    key: str = Field(pattern=r"^S\d{2}$", description="S01, S02, ...")
    beat: Beat
    location: str = Field(max_length=120)
    summary: str = Field(max_length=300)
    lines: list[ScriptLine] = Field(min_length=1)
    sound_cues: list[str] = Field(default_factory=list)
    visual_opportunities: list[str] = Field(default_factory=list)


class ScriptDraft(BaseModel):
    """What the LLM returns (structured output)."""

    title_working: str = Field(max_length=100)
    learning_objectives: list[str] = Field(min_length=1, max_length=4)
    scenes: list[ScriptScene] = Field(min_length=6, max_length=24)


class LineRef(BaseModel):
    line_id: str  # S01-L01
    scene_key: str
    speaker: Speaker
    text: str
    emotion: Emotion
    claim_ids: list[str]
    direction: str
    est_duration_s: float


class Script(BaseModel):
    """Stored artifact: the draft plus code-derived fields (line IDs, metrics)."""

    schema_version: Literal["script.v1"] = "script.v1"
    episode_slug: str
    version: int
    draft: ScriptDraft
    lines: list[LineRef]
    word_count: int
    est_duration_s: float
    readability: dict[str, float]
    validation_warnings: list[str] = Field(default_factory=list)
    revisions_used: int = 0
