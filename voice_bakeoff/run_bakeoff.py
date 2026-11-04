"""Kokoro-82M voice bake-off for Kai (hero) and Needle (companion).

Renders the same short original scene with several stock Kokoro voices, measures
CPU speed (real-time factor), checks whether word timestamps are available
(needed for subtitles and lip-sync), and writes a listening page.

Usage:  uv run python voice_bakeoff/run_bakeoff.py
Output: voice_bakeoff/output/ (gitignored) -> open index.html and listen.
"""

from __future__ import annotations

import html
import json
import platform
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24_000
OUT = Path(__file__).parent / "output"

# Original test scene (Question -> Adventure beat), written for this bake-off.
KAI_LINES = [
    "Okay, Needle, here's today's mystery. Why is the sky blue... and not purple, or green?",
    "Wait. You're telling me sunlight is secretly every color mixed together?",
    "Mystery: solved... almost!",
]
NEEDLE_LINES = [
    "Ooh! Ooh! Can we shrink down and ride a sunbeam to find out?",
    "Yep! And the blue light bounces around the most. Boing, boing, boing!",
]

# Stock voices only: no cloning, so no likeness-rights issues (DECISIONS.md D2).
KAI_CANDIDATES = {
    "af_heart": ("a", 1.0),
    "af_bella": ("a", 1.0),
    "af_nicole": ("a", 1.0),
    "am_puck": ("a", 1.0),
    "am_echo": ("a", 1.0),
    "bf_emma": ("b", 1.0),
}
NEEDLE_CANDIDATES = {
    "af_sky": ("a", 1.1),
    "am_puck": ("a", 1.15),
    "af_jessica": ("a", 1.1),
}


def synth(pipelines: dict[str, KPipeline], lang: str, voice: str, speed: float, text: str):
    pipe = pipelines.setdefault(lang, KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M"))
    chunks, words = [], []
    offset = 0.0
    t0 = time.perf_counter()
    for result in pipe(text, voice=voice, speed=speed):
        audio = result.audio
        if audio is None:
            continue
        audio = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
        for tok in getattr(result, "tokens", None) or []:
            start, end = getattr(tok, "start_ts", None), getattr(tok, "end_ts", None)
            if start is not None and end is not None:
                words.append({"text": tok.text, "start": round(offset + start, 3),
                              "end": round(offset + end, 3)})
        chunks.append(audio)
        offset += len(audio) / SAMPLE_RATE
    elapsed = time.perf_counter() - t0
    wav = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
    return wav, elapsed, words


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pipelines: dict[str, KPipeline] = {}
    synth(pipelines, "a", "af_heart", 1.0, "Warm up.")  # load model once before timing
    rows = []

    def render(role: str, voice: str, lang: str, speed: float, lines: list[str]) -> None:
        gap = np.zeros(int(0.35 * SAMPLE_RATE), dtype=np.float32)
        parts, total_t, all_words = [], 0.0, []
        for line in lines:
            wav, t, words = synth(pipelines, lang, voice, speed, line)
            parts += [wav, gap]
            total_t += t
            all_words += words
        audio = np.concatenate(parts)
        path = OUT / f"{role}_{voice}.wav"
        sf.write(path, audio, SAMPLE_RATE)
        dur = len(audio) / SAMPLE_RATE
        peak = float(np.max(np.abs(audio)))
        rows.append({"role": role, "voice": voice, "speed": speed, "file": path.name,
                     "audio_s": round(dur, 2), "compute_s": round(total_t, 2),
                     "x_realtime": round(dur / total_t, 2), "peak": round(peak, 3),
                     "word_timestamps": len(all_words)})
        print(f"{role:7} {voice:11} {dur:5.1f}s audio in {total_t:5.1f}s "
              f"({dur / total_t:4.1f}x realtime) words_ts={len(all_words)}")

    for voice, (lang, speed) in KAI_CANDIDATES.items():
        render("kai", voice, lang, speed, KAI_LINES)
    for voice, (lang, speed) in NEEDLE_CANDIDATES.items():
        render("needle", voice, lang, speed, NEEDLE_LINES)

    # Two sample duo pairings, interleaving lines as a real scene would.
    for kai_v, needle_v in [("af_heart", "af_sky"), ("am_echo", "am_puck")]:
        gap = np.zeros(int(0.3 * SAMPLE_RATE), dtype=np.float32)
        order = [(kai_v, KAI_LINES[0]), (needle_v, NEEDLE_LINES[0]), (kai_v, KAI_LINES[1]),
                 (needle_v, NEEDLE_LINES[1]), (kai_v, KAI_LINES[2])]
        parts = []
        for v, line in order:
            lang, speed = KAI_CANDIDATES[v] if v == kai_v else NEEDLE_CANDIDATES[v]
            wav, _, _ = synth(pipelines, lang, v, speed, line)
            parts += [wav, gap]
        sf.write(OUT / f"duo_{kai_v}+{needle_v}.wav", np.concatenate(parts), SAMPLE_RATE)

    meta = {"machine": platform.processor() or platform.machine(), "rows": rows}
    (OUT / "results.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_page(rows)


def write_page(rows: list[dict]) -> None:
    def block(title: str, files: list[tuple[str, str]]) -> str:
        items = "".join(
            f"<div class='c'><b>{html.escape(label)}</b><audio controls src='{html.escape(f)}'>"
            f"</audio></div>" for label, f in files
        )
        return f"<h2>{title}</h2><div class='g'>{items}</div>"

    kai = [(f"{r['voice']} · {r['x_realtime']}× realtime", r["file"])
           for r in rows if r["role"] == "kai"]
    needle = [(f"{r['voice']} (speed {r['speed']})", r["file"])
              for r in rows if r["role"] == "needle"]
    duos = [(p.stem.replace("duo_", ""), p.name) for p in sorted(OUT.glob("duo_*.wav"))]
    page = f"""<!doctype html><meta charset="utf-8"><title>Voice bake-off: Kai & Needle</title>
<style>body{{font-family:system-ui;background:#F4F0E8;color:#243B75;
max-width:960px;margin:2rem auto;padding:0 1rem}}
h1{{margin-bottom:.2rem}} h2{{border-bottom:3px solid #F8C84A;padding-bottom:.2rem}}
.g{{display:grid;gap:.8rem;
grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
.c{{background:#fff;border-radius:12px;padding:.8rem;box-shadow:0 1px 3px #0002}}
audio{{width:100%;margin-top:.4rem}}</style>
<h1>Voice bake-off: Kai &amp; Needle</h1>
<p>Kokoro-82M, stock voices, CPU only. Pick one voice for Kai and one for Needle.</p>
{block("Kai (hero, ~10 years old)", kai)}
{block("Needle (holographic spark)", needle)}
{block("Sample duo scenes", duos)}"""
    (OUT / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
