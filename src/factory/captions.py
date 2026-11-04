"""On-screen caption chunking (owner decision D7).

Kid-friendly rules: big text, so at most 2 lines of ~30 characters and at most 3 s per
chunk; break after sentence ends; never mix speakers in one chunk. Words keep their
script spelling and punctuation, so on-screen text always equals the script.
"""

from __future__ import annotations

import re

from factory.schemas.renderplan import PlanCaption, PlanWord

MAX_LINE_CHARS = 30
MAX_LINES = 2
MAX_CHUNK_FRAMES = 90  # 3 s at 30 fps
_SENTENCE_END = re.compile(r"[.!?…]['\"]?$")


def text_len(words: list[PlanWord]) -> int:
    return len(" ".join(w.text for w in words))


def _lines(words: list[PlanWord]) -> list[list[PlanWord]] | None:
    """Split words into <= 2 balanced lines of <= MAX_LINE_CHARS, or None if impossible."""
    if text_len(words) <= MAX_LINE_CHARS:
        return [words]
    best = None
    for i in range(1, len(words)):
        a, b = words[:i], words[i:]
        if text_len(a) <= MAX_LINE_CHARS and text_len(b) <= MAX_LINE_CHARS:
            score = abs(text_len(a) - text_len(b))
            if best is None or score < best[0]:
                best = (score, [a, b])
    return best[1] if best else None


def chunk_line(speaker: str, words: list[PlanWord]) -> list[PlanCaption]:
    chunks: list[PlanCaption] = []
    current: list[PlanWord] = []

    def flush() -> None:
        if current:
            lines = _lines(current) or [current]
            chunks.append(PlanCaption(speaker=speaker, start_frame=current[0].start_frame,  # type: ignore[arg-type]
                                      end_frame=current[-1].end_frame, lines=lines))
            current.clear()

    for w in words:
        candidate = [*current, w]
        too_long = _lines(candidate) is None
        too_slow = bool(current) and w.end_frame - current[0].start_frame > MAX_CHUNK_FRAMES
        if current and (too_long or too_slow):
            flush()
        current.append(w)
        if _SENTENCE_END.search(w.text) and text_len(current) >= 14:
            flush()
    flush()
    # Hold each chunk until the next one starts (no flicker between words of one line).
    for a, b in zip(chunks, chunks[1:], strict=False):
        a.end_frame = max(a.end_frame, b.start_frame)
    return chunks
