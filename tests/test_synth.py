"""Procedural audio (factory.media.synth): SFX families, music bed, ducking, resampling."""

from __future__ import annotations

import numpy as np
import pytest

from factory.media import synth as S


@pytest.mark.parametrize(("sfx_id", "family"), [
    ("shrink_whoosh", "riser"), ("compass_click", "click"), ("portal_open", "portal"),
    ("soft_whoosh_wings", "whoosh"), ("cartoon_boing", "boing"), ("magic_shimmer", "sparkle"),
    ("journal_page_flip", "paper"), ("bump_thud_soft", "thud"), ("cheer_sparkle", "sparkle"),
    ("something_unknown", "pop"),
])
def test_sfx_family_keywords(sfx_id: str, family: str) -> None:
    assert S.sfx_family(sfx_id) == family


def test_every_family_renders_clean_clip() -> None:
    rng = np.random.default_rng(0)
    for family, _ in S.SFX_KEYWORDS:
        clip = S.sfx(family, rng)
        assert clip.dtype == np.float32 and 0 < clip.size <= 3 * S.SR, family
        assert np.isfinite(clip).all() and 0.5 < np.abs(clip).max() <= 0.9 + 1e-6, family


def test_music_bed_is_deterministic_and_continuous() -> None:
    secs = [S.Section("curious", 0, 6), S.Section("adventure", 6, 12)]
    a = S.music_bed(secs, 12.0, "ep-x")
    b = S.music_bed(secs, 12.0, "ep-x")
    assert a.size == 12 * S.SR and np.array_equal(a, b)
    # No dead air at the scene boundary thanks to the crossfade.
    mid = a[int(5.5 * S.SR):int(6.5 * S.SR)]
    assert np.sqrt(np.mean(mid ** 2)) > 0.01


def test_duck_gain_dips_under_speech() -> None:
    voice = np.zeros(2 * S.SR, dtype=np.float32)
    voice[S.SR // 2:S.SR] = 0.3 * np.sin(np.arange(S.SR // 2) * 0.05)
    g = S.duck_gain(voice)
    assert g.size == voice.size
    assert g[int(0.1 * S.SR)] == pytest.approx(1.0, abs=0.01)  # silence: full music
    assert g[int(0.9 * S.SR)] < 0.4  # speech: music ducked
    assert g[int(1.9 * S.SR)] > 0.85  # released after speech


def test_upsample2_keeps_tone() -> None:
    sr = 24_000
    x = np.sin(2 * np.pi * 440 * np.arange(sr) / sr).astype(np.float32)
    y = S.upsample2(x)
    assert y.size == 2 * x.size
    spec = np.abs(np.fft.rfft(y * np.hanning(y.size)))
    assert np.fft.rfftfreq(y.size, 1 / S.SR)[int(np.argmax(spec))] == pytest.approx(440, abs=2)
