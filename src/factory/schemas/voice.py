"""Voice-over manifest and subtitle artifacts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from factory.schemas.characters import CharacterId


class Word(BaseModel):
    text: str
    start: float
    end: float


class VoiceLine(BaseModel):
    line_id: str
    speaker: CharacterId
    text: str
    voice: str
    speed: float
    file: str  # relative to content dir
    sha256: str
    duration_s: float
    est_duration_s: float
    preview_start_s: float  # position in the vo_preview track
    words: list[Word]
    stt_text: str
    wer: float
    word_errors: int
    peak_dbfs: float
    rms_dbfs: float
    cached: bool = False
    warnings: list[str] = Field(default_factory=list)


class VoiceManifest(BaseModel):
    schema_version: Literal["voice.v1"] = "voice.v1"
    episode_slug: str
    script_version: int
    sample_rate: int
    engine: str
    model: str
    licence: str
    stt_model: str
    gap_s: float
    lines: list[VoiceLine]
    preview_file: str
    total_speech_s: float
    preview_duration_s: float
    overall_wer: float
    warnings: list[str] = Field(default_factory=list)


class Cue(BaseModel):
    index: int
    start: float
    end: float
    speaker: str
    line_id: str
    lines: list[str] = Field(min_length=1, max_length=2)


class Subtitles(BaseModel):
    schema_version: Literal["subtitles.v1"] = "subtitles.v1"
    timeline: Literal["vo_preview"] = "vo_preview"  # the timing stage maps to the final cut
    cues: list[Cue]
    srt_file: str
    vtt_file: str
    warnings: list[str] = Field(default_factory=list)
