"""Fake TTS / STT for offline media tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from factory.providers.tts.base import TTSInfo, TTSResult, WordTiming


class FakeTTS:
    info = TTSInfo(engine="fake", model="fake-tts", license="Apache-2.0")

    def __init__(self, silent: bool = False):
        self.silent = silent
        self.calls: list[tuple[str, str, float]] = []

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:
        self.calls.append((text, voice, speed))
        sr = 24_000
        words = text.split()
        per_word = 0.4 / speed
        n = int(sr * per_word * len(words))
        t = np.arange(n) / sr
        audio = np.zeros(n, np.float32) if self.silent else (
            0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        timings = []
        for i, w in enumerate(words):
            timings.append(WordTiming(w.strip(".,!?"), round(i * per_word, 3),
                                      round((i + 1) * per_word, 3)))
            if w[-1] in ".,!?":
                timings.append(WordTiming(w[-1], round((i + 1) * per_word, 3),
                                          round((i + 1) * per_word, 3)))
        return TTSResult(audio=audio, sample_rate=sr, words=timings)


class FakeSTT:
    """Returns the script text for each clip (perfect STT) unless told otherwise."""

    model_name = "fake-stt"

    def __init__(self, texts: dict[str, str] | None = None, garble: bool = False):
        self.texts = texts or {}
        self.garble = garble
        self.by_file: dict[str, str] = {}

    def transcribe(self, path: Path, hint: str = "") -> str:
        if self.garble:
            return "completely different words here"
        return self.by_file.get(path.stem, self.texts.get(path.stem, ""))
