"""Small, dependency-light audio helpers (numpy + soundfile + ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

TARGET_RMS_DBFS = -20.0
PEAK_CEILING = 10 ** (-1.0 / 20)  # -1 dBFS
SILENCE_RMS_DBFS = -50.0


def dbfs(x: float) -> float:
    return 20 * np.log10(max(x, 1e-12))


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0


def peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio))) if audio.size else 0.0


def normalize(audio: np.ndarray, target_rms_dbfs: float = TARGET_RMS_DBFS) -> np.ndarray:
    """Match loudness between lines (RMS target), never exceeding -1 dBFS peak."""
    level = rms(audio)
    if level <= 0:
        return audio
    gain = 10 ** ((target_rms_dbfs - dbfs(level)) / 20)
    pk = peak(audio) * gain
    if pk > PEAK_CEILING:
        gain *= PEAK_CEILING / pk
    return (audio * gain).astype(np.float32)


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sample_rate, subtype="PCM_16")


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sr


def silence(seconds: float, sample_rate: int) -> np.ndarray:
    return np.zeros(int(round(seconds * sample_rate)), dtype=np.float32)


def load_16k_mono(path: Path) -> np.ndarray:
    """Decode any audio file to 16 kHz mono float32 via ffmpeg (for Whisper)."""
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise RuntimeError("ffmpeg not found on PATH")
    raw = subprocess.run(
        [exe, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()
