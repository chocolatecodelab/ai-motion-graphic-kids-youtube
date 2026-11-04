"""Text-to-speech provider interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class WordTiming:
    text: str
    start: float  # seconds from the start of the clip
    end: float


@dataclass(frozen=True)
class TTSResult:
    audio: np.ndarray  # mono float32, -1..1
    sample_rate: int
    words: list[WordTiming] = field(default_factory=list)


@dataclass(frozen=True)
class TTSInfo:
    engine: str
    model: str
    license: str


class TTSProvider(Protocol):
    info: TTSInfo

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult: ...
