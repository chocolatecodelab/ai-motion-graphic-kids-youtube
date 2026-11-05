"""Expressive, natural-sounding character voices on top of Kokoro (DECISIONS 2026-11-05).

Kokoro reads every line with the same pace and a narrow pitch range, and it has no child
voices. This module adds the acting:

- Emotion profiles: each script emotion sets a pace, a pitch offset and an intonation range.
- Sentence-level synthesis with punctuation-aware pauses, so lines breathe instead of rushing.
- Child voice via Praat's PSOLA "Change gender" (parselmouth): pitch median up to a boy's
  range, formants scaled up (a smaller vocal tract), and the pitch range widened. PSOLA keeps
  speech natural; a phase vocoder (rubberband) sounds metallic on voices.

parselmouth wraps Praat (GPL-3.0). It is used as a local processing tool; the audio it
produces is ours. Imported lazily so the rest of the factory does not depend on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Emotion:
    speed: float  # multiplies the character's base speed
    pitch_st: float  # semitones added to the character's pitch median
    range: float  # multiplies the character's pitch range (intonation width)


# Tuned for kids' animation: lively but never shouty; thoughtful lines slow down and settle.
EMOTIONS: dict[str, Emotion] = {
    "neutral": Emotion(0.94, 0.0, 1.00),
    "curious": Emotion(0.92, 0.6, 1.15),
    "excited": Emotion(1.00, 1.4, 1.30),
    "surprised": Emotion(0.95, 1.8, 1.35),
    "puzzled": Emotion(0.90, 0.2, 1.10),
    "determined": Emotion(0.95, -0.3, 1.00),
    "delighted": Emotion(0.97, 1.1, 1.25),
    "playful": Emotion(0.97, 0.9, 1.25),
    "thoughtful": Emotion(0.87, -0.6, 0.90),
}

PAUSES = {".": 0.30, "!": 0.32, "?": 0.36, "…": 0.45}
_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def emotion(name: str) -> Emotion:
    return EMOTIONS.get(name, EMOTIONS["neutral"])


def sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SPLIT.split(text.strip())) if s]


def pause_after(sentence: str) -> float:
    s = sentence.rstrip()
    if s.endswith("...") or s.endswith("…"):
        return PAUSES["…"]
    return PAUSES.get(s[-1:], 0.25)


@dataclass(frozen=True)
class VoiceStyle:
    """How a character sounds after Kokoro. pitch_hz=0 keeps Kokoro's pitch."""

    pitch_hz: float = 0.0  # target pitch median (a 10-year-old boy: ~220-250 Hz)
    formant: float = 1.0  # formant shift ratio (>1 = smaller, younger vocal tract)
    range: float = 1.0  # base pitch-range factor (>1 = livelier intonation)

    @property
    def active(self) -> bool:
        return self.pitch_hz > 0 or self.formant != 1.0 or self.range != 1.0


def change_voice(audio: np.ndarray, sr: int, pitch_hz: float, formant: float,
                 pitch_range: float, floor_hz: float = 70, ceiling_hz: float = 400) -> np.ndarray:
    """Praat PSOLA 'Change gender'. Same length out (duration factor 1)."""
    if audio.size < sr // 20:
        return audio
    import parselmouth
    from parselmouth.praat import call

    snd = parselmouth.Sound(audio.astype(np.float64), sampling_frequency=sr)
    try:
        out = call(snd, "Change gender", floor_hz, ceiling_hz, formant, pitch_hz, pitch_range,
                   1.0)
    except parselmouth.PraatError:
        # No analysable pitch (e.g. a whispered or very short sentence): formant-only change.
        try:
            out = call(snd, "Change gender", floor_hz, ceiling_hz, formant, 0, 1.0, 1.0)
        except parselmouth.PraatError:
            return audio
    y = np.asarray(out.values[0], dtype=np.float32)
    if int(round(out.sampling_frequency)) != sr:  # Praat may resample when shifting formants
        y = np.interp(np.linspace(0, y.size - 1, audio.size), np.arange(y.size), y)
    if y.size >= audio.size:
        return y[: audio.size].astype(np.float32)
    return np.concatenate([y, np.zeros(audio.size - y.size, np.float32)])


def pitch_stats(audio: np.ndarray, sr: int) -> tuple[float, float]:
    """(median F0 in Hz, intonation range = std of F0 in semitones) over voiced frames."""
    import parselmouth

    pitch = parselmouth.Sound(audio.astype(np.float64), sampling_frequency=sr).to_pitch(
        pitch_floor=70, pitch_ceiling=500)
    f0 = pitch.selected_array["frequency"]
    f0 = f0[f0 > 0]
    if f0.size < 5:
        return 0.0, 0.0
    st = 12 * np.log2(f0 / np.median(f0))
    return float(np.median(f0)), float(np.std(st))


def express(audio: np.ndarray, sr: int, style: VoiceStyle, emo: Emotion) -> np.ndarray:
    """Apply the character style plus the line's emotion (pitch offset, intonation range)."""
    if not style.active and emo.pitch_st == 0 and emo.range == 1.0:
        return audio
    base = style.pitch_hz or pitch_stats(audio, sr)[0]
    if base <= 0:
        return audio
    return change_voice(audio, sr, base * 2 ** (emo.pitch_st / 12), style.formant,
                        style.range * emo.range)