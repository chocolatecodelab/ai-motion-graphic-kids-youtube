from __future__ import annotations

from factory.captions import MAX_CHUNK_FRAMES, MAX_LINE_CHARS, chunk_line
from factory.schemas.renderplan import PlanWord


def words(text: str, start: int = 0, per: int = 8) -> list[PlanWord]:
    return [PlanWord(text=w, start_frame=start + i * per, end_frame=start + (i + 1) * per)
            for i, w in enumerate(text.split())]


def test_short_line_is_one_chunk() -> None:
    chunks = chunk_line("arka", words("Why is the sky blue?"))
    assert len(chunks) == 1 and len(chunks[0].lines) == 1


def test_long_line_splits_by_size_and_time_and_keeps_text() -> None:
    text = ("Light travels in waves. Each colour has its own wavelength. That's the length "
            "from one bump to the next.")
    chunks = chunk_line("lipa", words(text))
    assert len(chunks) >= 3
    for c in chunks:
        assert c.speaker == "lipa" and 1 <= len(c.lines) <= 2
        for line in c.lines:
            assert len(" ".join(w.text for w in line)) <= MAX_LINE_CHARS
        span = c.lines[-1][-1].end_frame - c.lines[0][0].start_frame
        assert span <= MAX_CHUNK_FRAMES + 8
    rebuilt = " ".join(w.text for c in chunks for line in c.lines for w in line)
    assert rebuilt == text
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a.end_frame == b.start_frame  # held until the next chunk, no flicker
