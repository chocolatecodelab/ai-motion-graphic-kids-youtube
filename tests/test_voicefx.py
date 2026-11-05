"""Expressive voice helpers: sentence split, pauses, emotion profiles, Praat boy voice."""

from __future__ import annotations

import numpy as np
import pytest

from factory.media import voicefx as V

SR = 24_000


def test_sentences_and_pauses() -> None:
    text = "Lipa, look at that sky. Why is it blue? Whoa! Mystery: solved... almost!"
    assert V.sentences(text) == ["Lipa, look at that sky.", "Why is it blue?", "Whoa!",
                                 "Mystery: solved...", "almost!"]
    assert V.pause_after("Why is it blue?") > V.pause_after("Look.")
    assert V.pause_after("solved...") == V.PAUSES["…"]


def test_emotions_slow_thoughtful_and_lift_excited() -> None:
    assert V.emotion("thoughtful").speed < V.emotion("excited").speed <= 1.0
    assert V.emotion("excited").pitch_st > 0 > V.emotion("thoughtful").pitch_st
    assert V.emotion("unknown") == V.EMOTIONS["neutral"]


def _voiced(f0: float, seconds: float = 1.2) -> np.ndarray:
    """A buzzy vowel-like tone with a gentle pitch glide (so Praat finds voicing)."""
    t = np.arange(int(seconds * SR)) / SR
    f = f0 * (1 + 0.05 * np.sin(2 * np.pi * 1.5 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    x = sum(np.sin(k * phase) / k for k in range(1, 12))
    return (0.2 * x).astype(np.float32)


def test_boy_style_raises_pitch_and_keeps_length() -> None:
    src = _voiced(120)
    out = V.express(src, SR, V.VoiceStyle(pitch_hz=235, formant=1.12, range=1.5),
                    V.emotion("neutral"))
    assert out.size == src.size and np.isfinite(out).all()
    f0, _ = V.pitch_stats(out, SR)
    assert f0 == pytest.approx(235, rel=0.08)


def test_inactive_style_and_neutral_is_identity() -> None:
    src = _voiced(150)
    assert V.express(src, SR, V.VoiceStyle(), V.Emotion(1.0, 0.0, 1.0)) is src
