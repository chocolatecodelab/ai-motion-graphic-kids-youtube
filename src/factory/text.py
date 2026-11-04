"""Deterministic text checks for kids' scripts: readability, timing, banned phrases."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Effective words/s for whole-episode word targets (~2.4 measured on the pilot incl. gaps).
WORDS_PER_SECOND = 2.5
LINE_GAP_S = 0.35
# Per-line clip duration model fitted on the pilot's 40 real Kokoro lines (2026-11-04):
# duration = overhead (lead/tail silence) + seconds_per_word * words / speed. MAE 0.32 s.
TTS_OVERHEAD_S = 1.0
SECONDS_PER_WORD = 0.28

_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:[.,]\d+)?")
_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)|…|\.\.\.")

BANNED_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(rx, re.IGNORECASE)
    for name, rx in {
        "lets_dive_in": r"\blet'?s dive (right )?in\b",
        "in_todays_video": r"\bin today'?s (video|episode)\b",
        "hey_guys": r"\bhey,? (guys|everyone|kids)\b",
        "like_subscribe": r"\b(like (and|&) subscribe|smash that|hit the bell|subscribe)\b",
        "comment_below": r"\b(comment|let us know) (below|in the comments)\b",
        "buckle_up": r"\bbuckle up\b",
        "without_further_ado": r"\bwithout further ado\b",
        "personal_info": r"\b(tell us|what'?s) your (name|age|address|school)\b",
        "only_smart_kids": r"\bonly (smart|clever) (kids|people)\b",
        "fake_urgency": r"\b(watch till the end|don'?t skip|you won'?t believe)\b",
    }.items()
}

UNSAFE_HINTS = re.compile(
    r"\b(try this at home|at home,? you can|matches|lighter|candle|bleach|stove|knife|"
    r"look (straight|directly) at the sun|electric(al)? socket)\b",
    re.IGNORECASE,
)
SAFETY_LINE = re.compile(r"\b(grown-?up|adult|parent|teacher)\b", re.IGNORECASE)


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def word_count(text: str) -> int:
    return len(words(text))


def count_syllables(word: str) -> int:
    w = word.lower()
    if w.isdigit():
        return max(1, len(w))  # rough: digits are read as words
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    groups = re.findall(r"[aeiouy]{1,2}", w)
    return max(1, len(groups))


def sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_END.split(text) if p and p.strip()]
    return [p for p in parts if words(p)]


@dataclass(frozen=True)
class Readability:
    words: int
    sentences: int
    avg_sentence_words: float
    fk_grade: float

    def as_dict(self) -> dict[str, float]:
        return {"words": self.words, "sentences": self.sentences,
                "avg_sentence_words": round(self.avg_sentence_words, 2),
                "fk_grade": round(self.fk_grade, 2)}


def readability(text_blocks: list[str]) -> Readability:
    """Flesch-Kincaid grade over spoken lines (each line counts as >= 1 sentence)."""
    n_words = n_sent = n_syll = 0
    for block in text_blocks:
        sents = sentences(block) or [block]
        for s in sents:
            ws = words(s)
            if not ws:
                continue
            n_sent += 1
            n_words += len(ws)
            n_syll += sum(count_syllables(w) for w in ws)
    if n_words == 0 or n_sent == 0:
        return Readability(0, 0, 0.0, 0.0)
    asl = n_words / n_sent
    grade = 0.39 * asl + 11.8 * (n_syll / n_words) - 15.59
    return Readability(n_words, n_sent, asl, grade)


def est_line_duration(text: str, speed: float = 1.0) -> float:
    return round(TTS_OVERHEAD_S + SECONDS_PER_WORD * word_count(text) / speed, 2)


def banned_hits(text: str) -> list[str]:
    return [name for name, rx in BANNED_PATTERNS.items() if rx.search(text)]
