"""Arka voice bake-off v2: natural boy voice with emotion (owner: "sounds robotic, flat, fast").

Fixes tried here:
- PSOLA (Praat "Change gender" via parselmouth) instead of a phase vocoder for the boy voice:
  pitch up, formants up (smaller vocal tract), wider intonation; or rubberband in its
  high-quality mode for comparison.
- Emotion profiles per line (pace, pitch offset, intonation range) from factory.media.voicefx.
- Sentence-level synthesis with punctuation-aware pauses.
Each candidate gets median pitch and intonation range (std of F0 in semitones; flat speech
is around 1.5-2, lively kids' animation 3+).

Usage:  uv run python voice_bakeoff/arka_voice_v2.py
Output: voice_bakeoff/output/arka_v2/ (gitignored) -> open index.html and listen.
"""

from __future__ import annotations

import html
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from factory.media import audio as A
from factory.media import voicefx as V
from factory.providers.tts.kokoro import KokoroTTS

SR = 24_000
OUT = Path(__file__).parent / "output" / "arka_v2"

LINES = [  # real pilot lines with their script emotions
    ("curious", "Lipa, look at that sky. Why is it blue? Why not purple, or green?"),
    ("excited", "Right. So where does the blue come from? Okay, Lipa, show me the inside!"),
    ("thoughtful", "Light travels in waves. Each colour has its own wavelength."),
    ("delighted", "That's why the whole sky looks blue!"),
]
LIPA = [("playful", "Maybe someone painted it!"),
        ("surprised", "Whoa! This sunbeam isn't white at all!")]

# id: (voice spec, base speed, processing, VoiceStyle or rubberband semitones)
CANDIDATES = {
    "REF_E_current": ("am_puck,af_heart", 1.0, "rubberband_fast", 3.0),
    "R_rubberband_hq": ("am_puck,af_heart", 1.0, "rubberband_hq", 3.0),
    "P1_puck_boy": ("am_puck", 1.0, "praat", V.VoiceStyle(pitch_hz=235, formant=1.12, range=1.5)),
    "P2_puck_boy_soft": ("am_puck", 1.0, "praat", V.VoiceStyle(pitch_hz=215, formant=1.08,
                                                               range=1.4)),
    "P3_echo_boy": ("am_echo", 1.0, "praat", V.VoiceStyle(pitch_hz=235, formant=1.12, range=1.5)),
    "P4_blend_boy": ("am_puck,af_heart", 1.0, "praat", V.VoiceStyle(pitch_hz=225, formant=1.05,
                                                                     range=1.5)),
}


def rubberband(audio: np.ndarray, st: float, hq: bool) -> np.ndarray:
    ratio = 2 ** (st / 12)
    opts = f"pitch={ratio:.6f}:formant=shifted" + (":pitchq=quality:window=short" if hq else "")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
         "-af", f"rubberband={opts}", "-f", "f32le", "-"],
        input=audio.astype(np.float32).tobytes(), capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32)
    return np.pad(y, (0, max(0, audio.size - y.size)))[: audio.size]


def line_audio(tts: KokoroTTS, voice: str, speed: float, mode: str, style, emo_name: str,
               text: str) -> np.ndarray:
    emo = V.emotion(emo_name) if mode != "rubberband_fast" else V.Emotion(1.0, 0.0, 1.0)
    parts = []
    sents = V.sentences(text) if mode != "rubberband_fast" else [text]
    for s in sents:
        a = tts.synthesize(s, voice, speed * emo.speed).audio
        a, _ = A.trim_silence(a, SR)
        if mode.startswith("rubberband"):
            a = rubberband(a, style, hq=mode == "rubberband_hq")
        elif mode == "praat":
            a = V.express(a, SR, style, emo)
        parts += [a, np.zeros(int(V.pause_after(s) * SR), np.float32)]
    return A.normalize(np.concatenate(parts[:-1]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tts = KokoroTTS()
    gap = np.zeros(int(0.5 * SR), np.float32)
    lipa_style = V.VoiceStyle(range=1.15)
    lipa = [V.express(A.trim_silence(tts.synthesize(t, "af_sky", 1.0 * V.emotion(e).speed).audio,
                                     SR)[0], SR, lipa_style, V.emotion(e)) for e, t in LIPA]
    rows = []
    for cid, (voice, speed, mode, style) in CANDIDATES.items():
        lines = [line_audio(tts, voice, speed, mode, style, e, t) for e, t in LINES]
        arka = np.concatenate([x for ln in lines for x in (ln, gap)])
        sf.write(OUT / f"{cid}.wav", arka, SR)
        duo = np.concatenate([lines[0], gap, A.normalize(lipa[0]), gap, lines[1], gap,
                              A.normalize(lipa[1])])
        sf.write(OUT / f"{cid}_duo.wav", duo, SR)
        f0, rng = V.pitch_stats(arka, SR)
        secs = sum(ln.size for ln in lines) / SR
        rows.append((cid, voice, mode, f0, rng, secs))
        print(f"{cid:18s} {mode:16s} F0={f0:5.0f} Hz  intonation={rng:4.2f} st  "
              f"speech={secs:4.1f}s")
    table = "\n".join(
        f"<tr><td><b>{html.escape(c)}</b><br><small>{html.escape(v)} · {m}</small></td>"
        f"<td>{f0:.0f} Hz</td><td>{r:.2f} st</td><td>{s:.1f}s</td>"
        f"<td><audio controls src='{c}.wav'></audio></td>"
        f"<td><audio controls src='{c}_duo.wav'></audio></td></tr>"
        for c, v, m, f0, r, s in rows)
    (OUT / "index.html").write_text(
        "<meta charset='utf-8'><title>Arka voice bake-off v2</title><style>body{font-family:"
        "sans-serif;margin:32px}td{padding:8px 12px;border-bottom:1px solid #ddd}</style>"
        "<h1>Arka voice bake-off v2</h1><p>4 pilot lines: curious, excited, thoughtful, "
        "delighted. Intonation = pitch variation (flat is about 1.5-2 st). Duo column adds "
        "Lipa (af_sky with emotion).</p><table><tr><th>candidate</th><th>median F0</th>"
        f"<th>intonation</th><th>length</th><th>Arka</th><th>with Lipa</th></tr>{table}</table>",
        encoding="utf-8")
    print("open", OUT / "index.html")


if __name__ == "__main__":
    main()
