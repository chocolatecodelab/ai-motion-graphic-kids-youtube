"""Local speech-to-text (faster-whisper, CPU int8) and word error rate for QA."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Protocol

from factory.media.audio import load_16k_mono

NUMBER_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
                "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def normalize_words(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[-–—/]", " ", text)
    text = re.sub(r"[^a-z0-9' ]", " ", text)
    words = [w.strip("'") for w in text.split()]
    return [NUMBER_WORDS.get(w, w) for w in words if w]


def wer(reference: str, hypothesis: str) -> tuple[float, int]:
    """(word error rate, number of errors) via Levenshtein distance over words."""
    ref, hyp = normalize_words(reference), normalize_words(hypothesis)
    if not ref:
        return (0.0 if not hyp else 1.0), len(hyp)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    errors = prev[-1]
    return errors / len(ref), errors


class Transcriber(Protocol):
    model_name: str

    def transcribe(self, path: Path, hint: str = "") -> str: ...


class WordTranscriber(Protocol):
    model_name: str

    def transcribe_words(self, path: Path, hint: str = "") -> list[tuple[str, float, float]]: ...


class WhisperTranscriber:
    def __init__(self, model_name: str = "base.en"):
        self.model_name = model_name
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            return self._model

    def transcribe(self, path: Path, hint: str = "") -> str:
        segments, _ = self._load().transcribe(
            load_16k_mono(path), language="en", beam_size=5,
            initial_prompt=hint or None, condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def transcribe_words(self, path: Path, hint: str = "") -> list[tuple[str, float, float]]:
        """(word, start_s, end_s) for every recognised word (used for subtitle sync QA)."""
        segments, _ = self._load().transcribe(
            load_16k_mono(path), language="en", beam_size=5, word_timestamps=True,
            initial_prompt=hint or None, condition_on_previous_text=False, vad_filter=False,
        )
        return [(w.word.strip(), float(w.start), float(w.end))
                for s in segments for w in (s.words or []) if w.word.strip()]
