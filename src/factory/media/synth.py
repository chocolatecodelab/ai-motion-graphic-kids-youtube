"""Procedural audio: sound effects and a gentle music bed, synthesised with numpy.

Free and original (DECISIONS D2: no stock libraries, no licence questions). Everything is
deterministic for a given seed, so re-renders are identical and cacheable.

- `sfx(family, rng)`: about 14 cartoon SFX families. Storyboard SFX ids are free-form
  ("shrink_whoosh", "compass_click"), so `sfx_family()` maps them by keyword.
- `music_bed(sections, total_s, seed)`: one steady tempo and key per episode; each scene's
  mood picks the chords and instruments, and sections crossfade at scene boundaries.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

SR = 48_000
TAU = 2 * np.pi

# --------------------------------------------------------------------------- helpers


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(round(seconds * SR))) / SR


def _env(n: int, attack: float, release: float, curve: float = 4.0) -> np.ndarray:
    """Attack ramp then exponential decay to silence over the clip."""
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    tail = np.exp(-curve * np.clip(t - attack, 0, None) / max(release, 1e-4))
    fade = np.clip((n - np.arange(n)) / (0.004 * SR), 0, 1)  # click-free end
    return a * tail * fade


def _fft_filter(x: np.ndarray, lo: float = 0.0, hi: float = SR / 2) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(x.size, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, n=x.size)


def _swept_noise(seconds: float, f0: float, f1: float, width: float,
                 rng: np.random.Generator) -> np.ndarray:
    """Noise whose band centre glides from f0 to f1 (STFT overlap-add): whooshes, wind."""
    n, hop, win = int(seconds * SR), 512, 2048
    frames = max(1, (n - win) // hop + 1)
    out = np.zeros(n + win)
    w = np.hanning(win)
    f = np.fft.rfftfreq(win, 1 / SR)
    for k in range(frames):
        p = k / max(1, frames - 1)
        c = f0 * (f1 / f0) ** p
        mag = np.exp(-0.5 * ((f - c) / (width * c)) ** 2)
        spec = mag * np.exp(1j * rng.uniform(0, TAU, f.size))
        out[k * hop:k * hop + win] += np.fft.irfft(spec, n=win) * w
    out = out[:n]
    return out / (np.max(np.abs(out)) + 1e-9)


def _tone(freq: float | np.ndarray, seconds: float, partials=((1, 1.0),)) -> np.ndarray:
    t = _t(seconds)
    phase = TAU * np.cumsum(np.broadcast_to(freq, t.shape)) / SR
    return sum(a * np.sin(phase * r) for r, a in partials)


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    return (x * (peak / (np.max(np.abs(x)) + 1e-9))).astype(np.float32)


# --------------------------------------------------------------------------- SFX

SFX_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("portal", ("portal", "vortex", "warp")),
    ("riser", ("shrink", "grow", "zoom", "time_jump", "timejump", "rise", "riser")),
    ("whoosh", ("whoosh", "swoosh", "swish", "wing", "flutter", "fly", "zip", "swoop")),
    ("boing", ("boing", "bounce", "spring", "bonk")),
    ("click", ("click", "tap", "tick", "latch", "snap")),
    ("sparkle", ("sparkle", "shimmer", "magic", "twinkle", "glow", "glitter", "peel")),
    ("chime", ("chime", "ding", "ping", "bell", "wiggle")),
    ("pop", ("pop", "bubble", "blip")),
    ("thud", ("thud", "bump", "impact", "thump", "land")),
    ("pluck", ("pluck", "curious", "question", "hmm", "bloop")),
    ("fanfare", ("cheer", "fanfare", "success", "tada", "victory", "celebrat")),
    ("wind", ("wind", "breeze", "air", "alien")),
    ("hum", ("hum", "drone", "wave")),
    ("paper", ("page", "flip", "paper", "rustle", "map", "fold")),
]


def sfx_family(sfx_id: str) -> str:
    s = sfx_id.lower()
    for family, words in SFX_KEYWORDS:
        if any(w in s for w in words):
            return family
    return "pop"


def seed_of(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "little")


def sfx(family: str, rng: np.random.Generator, variant: str = "") -> np.ndarray:
    """One SFX clip (mono float32 at SR, peak 0.9). `variant` tweaks direction (e.g. shrink)."""
    v = variant.lower()
    if family == "whoosh":
        x = _swept_noise(0.55, 500, 2600, 0.35, rng) * _env(int(0.55 * SR), 0.18, 0.35, 3)
    elif family == "riser":
        up = not any(w in v for w in ("shrink", "down"))
        f0, f1 = (300, 1800) if up else (1800, 300)
        n = int(0.9 * SR)
        x = 0.7 * _swept_noise(0.9, f0, f1, 0.25, rng) + 0.35 * _tone(
            np.geomspace(f0 / 2, f1 / 2, n), 0.9, ((1, 1), (2, 0.3)))
        x *= np.minimum(np.linspace(0.2, 1, n), _env(n, 0.6, 0.3, 3) + 0.05)
    elif family == "boing":
        n = int(0.5 * SR)
        t = _t(0.5)
        f = 180 * (1 + 0.6 * np.exp(-t * 9)) * (1 + 0.08 * np.sin(TAU * 14 * t))
        x = _tone(f, 0.5, ((1, 1), (2, 0.25))) * _env(n, 0.005, 0.45, 3.5)
    elif family == "click":
        n = int(0.06 * SR)
        x = (_fft_filter(rng.standard_normal(n), 1800, 9000) * _env(n, 0.001, 0.03, 6)
             + 0.6 * _tone(2400, 0.06) * _env(n, 0.001, 0.02, 6))
    elif family == "sparkle":
        x = np.zeros(int(0.9 * SR))
        for i in range(7):
            m = rng.choice([84, 86, 88, 91, 93, 96, 98])
            start = int((0.05 + i * 0.09 + rng.uniform(0, 0.03)) * SR)
            note = _tone(midi_hz(m), 0.35, ((1, 1), (2.76, 0.3), (5.4, 0.1))) * _env(
                int(0.35 * SR), 0.002, 0.3, 5)
            x[start:start + note.size] += note[: x.size - start] * (0.9 - i * 0.07)
    elif family == "chime":
        n = int(1.0 * SR)
        x = sum(_tone(midi_hz(m), 1.0, ((1, 1), (2.76, 0.4), (5.4, 0.15))) * g
                for m, g in ((84, 1.0), (91, 0.6))) * _env(n, 0.002, 0.9, 5)
    elif family == "pop":
        n = int(0.12 * SR)
        t = _t(0.12)
        x = _tone(900 * np.exp(-t * 12) + 300, 0.12) * _env(n, 0.002, 0.1, 5)
    elif family == "thud":
        n = int(0.35 * SR)
        t = _t(0.35)
        x = (_tone(110 * np.exp(-t * 8) + 45, 0.35) * _env(n, 0.002, 0.3, 4)
             + 0.25 * _fft_filter(rng.standard_normal(n), 60, 900) * _env(n, 0.001, 0.08, 6))
    elif family == "pluck":
        x = _karplus(midi_hz(rng.choice([67, 69, 72])), 0.6, rng)
    elif family == "fanfare":
        x = np.zeros(int(1.2 * SR))
        for i, m in enumerate((72, 76, 79, 84)):
            note = _tone(midi_hz(m), 0.7, ((1, 1), (2, 0.35), (3, 0.15))) * _env(
                int(0.7 * SR), 0.01, 0.6, 3)
            s = int(i * 0.11 * SR)
            x[s:s + note.size] += note[: x.size - s]
    elif family == "portal":
        n = int(1.4 * SR)
        swirl = _swept_noise(1.4, 250, 3000, 0.3, rng)
        lfo = 1 + 0.5 * np.sin(TAU * 6 * _t(1.4))
        tone = _tone(np.geomspace(220, 880, n), 1.4, ((1, 1), (1.5, 0.5), (2.01, 0.4)))
        x = (0.7 * swirl * lfo + 0.4 * tone) * _env(n, 0.5, 0.9, 3)
    elif family == "wind":
        n = int(2.2 * SR)
        x = _swept_noise(2.2, 350, 600, 0.6, rng) * (0.6 + 0.4 * np.sin(TAU * 0.7 * _t(2.2)))
        x *= np.minimum(np.linspace(0, 1, n) * 3, 1) * np.minimum(np.linspace(1, 0, n) * 3, 1)
    elif family == "hum":
        n = int(2.0 * SR)
        x = _tone(midi_hz(55) * (1 + 0.003 * np.sin(TAU * 0.8 * _t(2.0))), 2.0,
                  ((1, 1), (2, 0.5), (3, 0.25)))
        x *= np.minimum(np.linspace(0, 1, n) * 4, 1) * np.minimum(np.linspace(1, 0, n) * 4, 1)
    elif family == "paper":
        x = np.zeros(int(0.45 * SR))
        for i in range(4):
            n = int(rng.uniform(0.03, 0.07) * SR)
            burst = _fft_filter(rng.standard_normal(n), 1500, 8000) * _env(n, 0.003, 0.05, 4)
            s = int((i * 0.08 + rng.uniform(0, 0.02)) * SR)
            x[s:s + n] += burst[: x.size - s]
    else:
        return sfx("pop", rng)
    return _norm(np.asarray(x, dtype=np.float64))


def _karplus(freq: float, seconds: float, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * SR)
    period = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, period)
    out = np.empty(n)
    # Vectorised in blocks of one period (the averaging filter only looks back one period).
    for start in range(0, n, period):
        out[start:start + period] = buf[: min(period, n - start)]
        buf = 0.497 * (buf + np.roll(buf, 1))
    return out * _env(n, 0.001, seconds, 3)


# --------------------------------------------------------------------------- music


@dataclass(frozen=True)
class Section:
    mood: str
    start_s: float
    end_s: float


# Scale degrees (semitones from the key root) for each chord, one chord per bar.
CHORDS = {
    "I": (0, 4, 7), "ii": (2, 5, 9), "iii": (4, 7, 11), "IV": (5, 9, 12), "V": (7, 11, 14),
    "vi": (9, 12, 16), "Isus2": (0, 2, 7), "Isus4": (0, 5, 7), "bVII": (10, 14, 17),
    "IVadd9": (5, 9, 12, 19), "Iadd9": (0, 4, 7, 14),
}
MOODS: dict[str, dict] = {
    "curious": {"prog": ["vi", "IV", "I", "V"], "arp": 1, "bass": False, "perc": False,
                "bells": 0.15, "pad": 0.5},
    "adventure": {"prog": ["I", "V", "vi", "IV"], "arp": 2, "bass": True, "perc": True,
                  "bells": 0.1, "pad": 0.45},
    "wonder": {"prog": ["IVadd9", "Iadd9", "V", "vi"], "arp": 2, "bass": True, "perc": False,
               "bells": 0.45, "pad": 0.6},
    "mystery": {"prog": ["Isus2", "bVII", "IV", "Isus4"], "arp": 1, "bass": True, "perc": False,
                "bells": 0.3, "pad": 0.65},
    "warm": {"prog": ["I", "vi", "IV", "V"], "arp": 1, "bass": True, "perc": True,
             "bells": 0.15, "pad": 0.5},
}
BEAT_MOOD = {"hook": "curious", "mystery": "curious", "adventure": "adventure",
             "discovery": "wonder", "twist": "mystery", "takeaway": "warm"}
BPM = 96
XFADE_S = 1.2


def _add(buf: np.ndarray, start_s: float, clip: np.ndarray, gain: float) -> None:
    s = int(round(start_s * SR))
    if s >= buf.size or s + clip.size <= 0:
        return
    a, b = max(0, s), min(buf.size, s + clip.size)
    buf[a:b] += gain * clip[a - s:b - s]


def _render_mood(mood: str, start_s: float, end_s: float, root: int,
                 rng: np.random.Generator) -> np.ndarray:
    m = MOODS[mood]
    beat = 60 / BPM
    bar = 4 * beat
    out = np.zeros(int(round((end_s - start_s) * SR)) + 1)
    first_bar = int(np.floor(start_s / bar))
    last_bar = int(np.ceil(end_s / bar))
    pad_note = {}
    for b in range(first_bar, last_bar):
        chord = CHORDS[m["prog"][b % len(m["prog"])]]
        t0 = b * bar - start_s
        # pad: soft additive chord with slight detune, swelling over the bar
        for deg in chord[:3]:
            hz = midi_hz(root + 48 + 12 + deg)
            key = round(hz, 2)
            if key not in pad_note:
                n = int((bar + 0.6) * SR)
                tone = sum(_tone(hz * d, bar + 0.6, ((1, 1), (2, 0.35), (3, 0.12), (4, 0.06)))
                           for d in (0.9983, 1.0017)) / 2
                pad_note[key] = tone * np.minimum(_env(n, 0.45, bar, 1.2), 1)
            _add(out, t0, pad_note[key], 0.05 * m["pad"])
        # bass on beats 1 and 3
        if m["bass"]:
            hz = midi_hz(root + 36 + chord[0])
            note = _tone(hz, beat * 1.6, ((1, 1), (2, 0.3))) * _env(int(beat * 1.6 * SR), 0.01,
                                                                   beat * 1.4, 3)
            for k in (0, 2):
                _add(out, t0 + k * beat, note, 0.055)
        # marimba-like arpeggio
        steps = 4 * m["arp"]
        for k in range(steps):
            deg = chord[(k * (2 if k % 2 else 1)) % len(chord)] + (12 if k % 4 == 3 else 0)
            hz = midi_hz(root + 60 + deg)
            dur = 0.45
            note = _tone(hz, dur, ((1, 1), (3.9, 0.18), (9.2, 0.05))) * _env(
                int(dur * SR), 0.006, dur, 6)
            accent = 1.0 if k % m["arp"] == 0 else 0.7
            _add(out, t0 + k * beat / m["arp"], note, 0.07 * accent)
        # bells: an occasional high sparkle on the chord
        if rng.random() < m["bells"] * 2:
            deg = chord[int(rng.integers(len(chord)))]
            hz = midi_hz(root + 84 + deg)
            note = _tone(hz, 1.4, ((1, 1), (2.76, 0.3), (5.4, 0.1))) * _env(int(1.4 * SR),
                                                                            0.006, 1.3, 5)
            _add(out, t0 + beat * int(rng.integers(4)), note, 0.035)
        # light percussion: soft kick on 1 and 3, shaker on eighths
        if m["perc"]:
            kick_t = _t(0.18)
            kick = _tone(110 * np.exp(-kick_t * 22) + 48, 0.18) * _env(kick_t.size, 0.002, 0.15, 5)
            for k in (0, 2):
                _add(out, t0 + k * beat, kick, 0.045)
            for k in range(8):
                n = int(0.05 * SR)
                sh = rng.standard_normal(n) * _env(n, 0.004, 0.04, 5)
                _add(out, t0 + k * beat / 2, sh, 0.012 if k % 2 else 0.018)
    return out


def music_bed(sections: list[Section], total_s: float, seed: str) -> np.ndarray:
    """Whole-episode music bed: same tempo/key throughout, crossfaded mood sections."""
    rng = np.random.default_rng(seed_of(seed))
    root = int(rng.choice([0, 2, 3, 5, 7]))  # C, D, Eb, F, G
    total = np.zeros(int(round(total_s * SR)))
    for i, sec in enumerate(sections):
        mood = sec.mood if sec.mood in MOODS else "curious"
        a = max(0.0, sec.start_s - XFADE_S / 2)
        b = min(total_s, sec.end_s + XFADE_S / 2)
        if b <= a:
            continue
        part = _render_mood(mood, a, b, root, rng)[: int(round((b - a) * SR))]
        n = part.size
        g = np.ones(n)
        fade = int(XFADE_S * SR)
        if i > 0:
            k = min(fade, n)
            g[:k] = np.sin(np.linspace(0, np.pi / 2, k)) ** 2
        else:
            k = min(int(0.8 * SR), n)
            g[:k] = np.linspace(0, 1, k)
        if i < len(sections) - 1:
            k = min(fade, n)
            g[n - k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
        else:
            k = min(int(2.0 * SR), n)
            g[n - k:] *= np.linspace(1, 0, k)
        _add(total, a, part * g, 1.0)
    # gentle high cut so the bed never competes with speech sibilance
    total = _fft_filter(total, 45, 9000)
    return _norm(total, 0.8) if np.any(total) else total.astype(np.float32)


# --------------------------------------------------------------------------- mixing


def upsample2(x: np.ndarray) -> np.ndarray:
    """Exact 2x band-limited upsampling (FFT zero-padding): 24 kHz voice -> 48 kHz mix."""
    if x.size == 0:
        return x.astype(np.float32)
    spec = np.fft.rfft(x)
    out = np.fft.irfft(np.concatenate([spec, np.zeros(x.size + 1 - spec.size)]),
                       n=2 * x.size) * 2
    return out.astype(np.float32)


def duck_gain(voice: np.ndarray, depth: float = 0.72, attack_s: float = 0.06,
              release_s: float = 0.45) -> np.ndarray:
    """Music gain that dips while someone speaks (sidechain-style), smoothed at 200 Hz."""
    hop = SR // 200
    frames = int(np.ceil(voice.size / hop))
    padded = np.pad(np.abs(voice), (0, frames * hop - voice.size))
    env = padded.reshape(frames, hop).max(axis=1)
    target = 1 - depth * np.clip(env / 0.08, 0, 1)
    g = np.empty(frames)
    cur = 1.0
    a = np.exp(-1 / (attack_s * 200))
    r = np.exp(-1 / (release_s * 200))
    for i, tv in enumerate(target):
        coef = a if tv < cur else r
        cur = coef * cur + (1 - coef) * tv
        g[i] = cur
    return np.interp(np.arange(voice.size) / hop, np.arange(frames), g).astype(np.float32)
