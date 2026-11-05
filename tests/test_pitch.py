"""Pitch shift used to turn a male-led Kokoro blend into a boy's voice (Arka)."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from factory.media.audio import pitch_shift

SR = 24_000


def _has_rubberband() -> bool:
    exe = shutil.which("ffmpeg")
    if exe is None:
        return False
    out = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " rubberband " in out


def _dominant_hz(x: np.ndarray) -> float:
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return float(np.fft.rfftfreq(x.size, 1 / SR)[int(np.argmax(spec))])


def test_zero_shift_is_identity() -> None:
    x = np.random.default_rng(0).standard_normal(1000).astype(np.float32)
    assert pitch_shift(x, SR, 0) is x


@pytest.mark.skipif(not _has_rubberband(), reason="ffmpeg without rubberband")
def test_shift_keeps_length_and_raises_pitch() -> None:
    t = np.arange(SR) / SR
    tone = (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    up = pitch_shift(tone, SR, 12)
    assert up.size == tone.size  # duration preserved -> word timings stay valid
    assert _dominant_hz(up[2000:-2000]) == pytest.approx(400, rel=0.05)


def test_trim_silence_keeps_speech_and_reports_lead() -> None:
    from factory.media.audio import trim_silence

    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
    x = np.concatenate([np.zeros(SR // 2, np.float32), tone, np.zeros(SR, np.float32)])
    y, lead = trim_silence(x, SR)
    assert lead == pytest.approx(0.5 - 0.06, abs=0.011)
    assert y.size == pytest.approx(SR + 2 * 0.06 * SR, abs=0.011 * SR)