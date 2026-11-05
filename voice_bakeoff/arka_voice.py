"""Arka voice bake-off: a 10-year-old boy from Kokoro stock voices (no cloning, D2).

Kokoro has no child voices, so candidates are male stock voices, male/female blends
(Kokoro averages comma-separated voice packs) and pitch-raised versions (ffmpeg rubberband,
duration preserved so word timings stay valid). Each candidate gets a median pitch (F0)
measurement; a 10-year-old boy speaks around 230-270 Hz, an adult man around 100-140 Hz.

Usage:  uv run python voice_bakeoff/arka_voice.py
Output: voice_bakeoff/output/arka/ (gitignored) -> open index.html and listen.
"""

from __future__ import annotations

import html
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SR = 24_000
OUT = Path(__file__).parent / "output" / "arka"
LEXICON = {"Lipa": "lˈipə"}

LINES = [
    "Lipa, look at that sky! Why is it blue? Why not purple, or green?",
    "Here's my guess. Sunlight is blue, so the sky is blue.",
    "Whoa! It's all the colours of the rainbow, mixed together! Mystery: solved... almost!",
]
LIPA_LINE = "Maybe someone painted it!"

# id: (kokoro voice spec, speed, pitch semitones, formant mode)
CANDIDATES: dict[str, tuple[str, float, float, str]] = {
    "REF_af_heart_old": ("af_heart", 1.0, 0, ""),
    "A_puck_adult": ("am_puck", 1.05, 0, ""),
    "B_puck_plus6": ("am_puck", 1.05, 6, "shifted"),
    "C_puck2_heart1_plus4": ("am_puck,am_puck,af_heart", 1.05, 4, "shifted"),
    "D_puck2_heart1_plus6": ("am_puck,am_puck,af_heart", 1.05, 6, "shifted"),
    "E_puck_heart_plus3": ("am_puck,af_heart", 1.05, 3, "shifted"),
    "F_echo_puck_heart_plus4": ("am_echo,am_puck,af_heart", 1.05, 4, "shifted"),
    "G_puck_heart_plus5": ("am_puck,af_heart", 1.05, 5, "shifted"),
}


def lex(text: str) -> str:
    for w, p in LEXICON.items():
        text = text.replace(w, f"[{w}](/{p}/)")
    return text


def synth(pipe: KPipeline, voice: str, speed: float, text: str) -> np.ndarray:
    parts = [np.asarray(r.audio) for r in pipe(lex(text), voice=voice, speed=speed)
             if r.audio is not None]
    return np.concatenate(parts).astype(np.float32)


def pitch_shift(path: Path, semitones: float, formant: str) -> None:
    ratio = 2 ** (semitones / 12)
    tmp = path.with_suffix(".tmp.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-af",
                    f"rubberband=pitch={ratio:.5f}:formant={formant}", str(tmp)], check=True)
    tmp.replace(path)


def median_f0(audio: np.ndarray, sr: int = SR) -> float:
    """Autocorrelation pitch tracker over voiced 40 ms frames (70-450 Hz)."""
    win, hop = int(0.04 * sr), int(0.01 * sr)
    lo, hi = int(sr / 450), int(sr / 70)
    rms_all = np.sqrt(np.mean(audio ** 2)) + 1e-9
    f0s = []
    for i in range(0, len(audio) - win, hop):
        fr = audio[i:i + win] - np.mean(audio[i:i + win])
        if np.sqrt(np.mean(fr ** 2)) < 0.5 * rms_all:
            continue
        ac = np.correlate(fr, fr, "full")[win - 1:]
        if ac[0] <= 0:
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] / ac[0] > 0.45:
            f0s.append(sr / lag)
    return float(np.median(f0s)) if f0s else 0.0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    gap = np.zeros(int(0.45 * SR), dtype=np.float32)
    lipa = synth(pipe, "af_sky", 1.1, LIPA_LINE)
    rows = []
    for cid, (voice, speed, st, formant) in CANDIDATES.items():
        audio = np.concatenate([np.concatenate([synth(pipe, voice, speed, t), gap]) for t in LINES])
        path = OUT / f"{cid}.wav"
        sf.write(path, audio, SR)
        if st:
            pitch_shift(path, st, formant)
        arka, _ = sf.read(path, dtype="float32")
        f0 = median_f0(arka)
        sf.write(OUT / f"{cid}_duo.wav", np.concatenate([arka[: int(4.2 * SR)], gap, lipa]), SR)
        rows.append((cid, voice, speed, st, formant, f0))
        print(f"{cid:24s} voice={voice:26s} pitch={st:+.0f}st {formant or '-':9s} F0={f0:5.0f} Hz")
    items = "\n".join(
        f"<tr><td><b>{html.escape(c)}</b><br><small>{html.escape(v)} · speed {s} · "
        f"{f'{st:+g} semitones ({fm})' if st else 'no pitch shift'}</small></td>"
        f"<td>{f0:.0f} Hz</td><td><audio controls src='{c}.wav'></audio></td>"
        f"<td><audio controls src='{c}_duo.wav'></audio></td></tr>"
        for c, v, s, st, fm, f0 in rows)
    (OUT / "index.html").write_text(
        "<meta charset='utf-8'><title>Arka voice bake-off</title>"
        "<style>body{font-family:sans-serif;margin:32px}"
        "td{padding:8px 14px;border-bottom:1px solid #ddd}</style>"
        "<h1>Arka voice bake-off</h1><p>Target: a 10-year-old boy (about 230-270 Hz). "
        "Adult men are about 100-140 Hz. Right column: Arka, then Lipa (af_sky).</p>"
        "<table><tr><th>candidate</th><th>median F0</th><th>Arka</th><th>with Lipa</th></tr>"
        f"{items}</table>",
        encoding="utf-8")
    print("open", OUT / "index.html")


if __name__ == "__main__":
    main()
