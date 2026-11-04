"""Kokoro-82M, local CPU TTS (Apache-2.0). Stock voices only (DECISIONS.md D2).

Pronunciation overrides use Kokoro/misaki's inline syntax `[word](/phonemes/)`,
applied from config/pronunciations.yaml.
"""

from __future__ import annotations

import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from factory.providers.tts.base import TTSInfo, TTSResult, WordTiming
from factory.resources import ROOT

REPO_ID = "hexgrad/Kokoro-82M"
SAMPLE_RATE = 24_000
LEXICON_FILE = ROOT / "config" / "pronunciations.yaml"


@lru_cache(maxsize=1)
def load_lexicon(path: Path = LEXICON_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in (data.get("words") or {}).items()}


def apply_lexicon(text: str, lexicon: dict[str, str]) -> str:
    for word, phonemes in sorted(lexicon.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"(?<![\w\[]){re.escape(word)}(?![\w\]])", f"[{word}](/{phonemes}/)",
                      text)
    return text


class KokoroTTS:
    info = TTSInfo(engine="kokoro", model=REPO_ID, license="Apache-2.0")

    def __init__(self, lexicon: dict[str, str] | None = None):
        self.lexicon = load_lexicon() if lexicon is None else lexicon
        self._pipelines: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _pipeline(self, voice: str) -> Any:
        lang = voice[0]  # 'a' = American English, 'b' = British English
        with self._lock:
            if lang not in self._pipelines:
                from kokoro import KPipeline  # heavy import (torch): only when used

                self._pipelines[lang] = KPipeline(lang_code=lang, repo_id=REPO_ID)
            return self._pipelines[lang]

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:
        chunks: list[np.ndarray] = []
        words: list[WordTiming] = []
        offset = 0.0
        for result in self._pipeline(voice)(apply_lexicon(text, self.lexicon), voice=voice,
                                            speed=speed):
            if result.audio is None:
                continue
            audio = result.audio.numpy() if hasattr(result.audio, "numpy") else np.asarray(
                result.audio)
            for tok in getattr(result, "tokens", None) or []:
                start, end = getattr(tok, "start_ts", None), getattr(tok, "end_ts", None)
                if start is None or end is None:
                    continue
                words.append(WordTiming(tok.text, round(offset + start, 3),
                                        round(offset + end, 3)))
            chunks.append(audio.astype(np.float32))
            offset += len(audio) / SAMPLE_RATE
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return TTSResult(audio=audio, sample_rate=SAMPLE_RATE, words=words)
