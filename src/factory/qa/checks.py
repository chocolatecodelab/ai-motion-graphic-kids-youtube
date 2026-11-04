"""Deterministic technical QA checks on a finished episode (docs/AGENT_SPECIFICATIONS §10).

Each check returns one or more `Check` results. Severity `critical` blocks publication.
Pure functions over files + plan data, so each one can be tested with seeded defects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Literal

from factory.media import ffmpeg
from factory.media.stt import normalize_words, wer

Severity = Literal["critical", "warning", "info"]
Status = Literal["pass", "fail", "warn"]


@dataclass
class Check:
    id: str
    category: Literal["technical", "video", "audio", "speech", "subtitles", "content", "rights"]
    status: Status
    severity: Severity
    detail: str
    fix_stage: str | None = None  # which pipeline stage to re-run when this fails
    data: dict[str, object] = field(default_factory=dict)


def ok(id_: str, cat, detail: str, **data: object) -> Check:  # type: ignore[no-untyped-def]
    return Check(id_, cat, "pass", "info", detail, data=dict(data))


def fail(id_: str, cat, detail: str, fix: str | None = None, **data: object) -> Check:  # type: ignore[no-untyped-def]
    return Check(id_, cat, "fail", "critical", detail, fix, dict(data))


def warn(id_: str, cat, detail: str, fix: str | None = None, **data: object) -> Check:  # type: ignore[no-untyped-def]
    return Check(id_, cat, "warn", "warning", detail, fix, dict(data))


# ---------------------------------------------------------------- spec


def check_spec(video: Path, expected: dict[str, object], expected_duration: float) -> list[Check]:
    info = ffmpeg.video_info(video)
    out: list[Check] = []
    want_res = (expected["width"], expected["height"])
    got_res = (info.get("width"), info.get("height"))
    out.append(ok("spec.resolution", "technical", f"{got_res[0]}x{got_res[1]}")
               if got_res == want_res else
               fail("spec.resolution", "technical", f"{got_res[0]}x{got_res[1]}, expected "
                    f"{want_res[0]}x{want_res[1]}", "render_scenes"))
    fps = round(float(info.get("fps", 0)), 2)
    out.append(ok("spec.fps", "technical", f"{fps} fps") if abs(fps - float(expected["fps"])) < 0.01
               else fail("spec.fps", "technical", f"{fps} fps, expected {expected['fps']}",
                         "render_scenes"))
    codecs = (info.get("vcodec"), info.get("pix_fmt"), info.get("acodec"))
    out.append(ok("spec.codecs", "technical", "H.264 yuv420p + AAC")
               if codecs == ("h264", "yuv420p", "aac") else
               fail("spec.codecs", "technical", f"got {codecs}", "assemble"))
    sr = info.get("sample_rate")
    out.append(ok("spec.audio_rate", "technical", f"{sr} Hz") if sr == 48000 else
               warn("spec.audio_rate", "technical", f"{sr} Hz, expected 48000", "assemble"))
    drift = abs(float(info["duration"]) - expected_duration)
    out.append(ok("spec.duration", "technical", f"{info['duration']:.2f}s (plan "
                  f"{expected_duration:.2f}s)") if drift <= 0.15 else
               fail("spec.duration", "technical", f"{info['duration']:.2f}s vs plan "
                    f"{expected_duration:.2f}s", "assemble"))
    return out


def check_decode(video: Path) -> Check:
    proc = ffmpeg.run(["-v", "error", "-i", str(video), "-f", "null", "-"])
    errors = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    return (ok("decode.clean", "technical", "decodes without errors") if not errors else
            fail("decode.clean", "technical", f"{len(errors)} decode errors: {errors[0][:160]}",
                 "render_scenes"))


# ---------------------------------------------------------------- picture + sound scans

@dataclass
class Scan:
    black: list[tuple[float, float]]
    freeze: list[tuple[float, float]]
    silence: list[tuple[float, float]]


def scan(video: Path, black_min_s: float = 0.5, freeze_min_s: float = 2.0,
         silence_min_s: float = 0.6) -> Scan:
    """One decode pass: blackdetect + freezedetect on video, silencedetect on audio."""
    proc = ffmpeg.run([
        "-i", str(video),
        "-vf", f"blackdetect=d={black_min_s}:pix_th=0.10,freezedetect=n=-60dB:d={freeze_min_s}",
        "-af", f"silencedetect=noise=-45dB:d={silence_min_s}",
        "-f", "null", "-"])
    err = proc.stderr
    black = [(float(a), float(b)) for a, b in
             re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", err)]
    fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", err)]
    ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    duration = float(ffmpeg.video_info(video)["duration"])
    freeze = [(s, fe[i] if i < len(fe) else duration) for i, s in enumerate(fs)]
    silence = [(max(0.0, s), se[i] if i < len(se) else duration) for i, s in enumerate(ss)]
    return Scan(black, freeze, silence)


def check_black(s: Scan) -> Check:
    if not s.black:
        return ok("video.black_frames", "video", "no black segments")
    worst = max(s.black, key=lambda r: r[1] - r[0])
    return fail("video.black_frames", "video",
                f"{len(s.black)} black segment(s); longest {worst[1] - worst[0]:.2f}s at "
                f"{worst[0]:.2f}s", "render_scenes", segments=s.black)


def check_freeze(s: Scan) -> Check:
    if not s.freeze:
        return ok("video.frozen", "video", "no frozen segments over 2 s")
    worst = max(s.freeze, key=lambda r: r[1] - r[0])
    return warn("video.frozen", "video",
                f"{len(s.freeze)} frozen segment(s); longest {worst[1] - worst[0]:.1f}s at "
                f"{worst[0]:.1f}s (static shot without motion?)", "storyboard",
                segments=s.freeze)


def check_silence(s: Scan, speech: list[tuple[float, float]],
                  long_gap_s: float = 2.5) -> list[Check]:
    """Silence inside a voice line = dropout (critical). Long gaps between lines = warning
    (no music bed yet)."""
    out: list[Check] = []
    dropouts = []
    for a, b in s.silence:
        for la, lb in speech:
            overlap = min(b, lb - 0.15) - max(a, la + 0.15)  # ignore natural edges
            if overlap > 0.35:
                dropouts.append((round(max(a, la), 2), round(min(b, lb), 2)))
                break
    out.append(ok("audio.dropouts", "audio", "no silence inside voice lines") if not dropouts
               else fail("audio.dropouts", "audio", f"silence inside {len(dropouts)} voice "
                         f"line(s), first at {dropouts[0][0]}s", "assemble", segments=dropouts))
    long_gaps = [(round(a, 1), round(b, 1)) for a, b in s.silence if b - a >= long_gap_s]
    out.append(ok("audio.long_gaps", "audio", f"no silent gap over {long_gap_s}s")
               if not long_gaps else
               warn("audio.long_gaps", "audio", f"{len(long_gaps)} silent gap(s) over "
                    f"{long_gap_s}s (music bed not mixed yet)", "assemble", segments=long_gaps))
    return out


def check_loudness(video: Path, target: float = -14.0) -> list[Check]:
    m = ffmpeg.measure_loudness(video)
    i, tp = m["integrated_lufs"], m["true_peak_dbtp"]
    out = [ok("audio.loudness", "audio", f"{i} LUFS (target {target} ±1)") if abs(i - target) <= 1
           else fail("audio.loudness", "audio", f"{i} LUFS, target {target} ±1", "assemble")]
    if tp > -0.5:
        out.append(fail("audio.true_peak", "audio", f"true peak {tp} dBTP: clipping risk",
                        "assemble"))
    elif tp > -0.9:
        out.append(warn("audio.true_peak", "audio", f"true peak {tp} dBTP (aim ≤ -1)", "assemble"))
    else:
        out.append(ok("audio.true_peak", "audio", f"true peak {tp} dBTP"))
    return out


# ---------------------------------------------------------------- speech + subtitles


def check_speech(script_text: str, heard: str) -> Check:
    rate, errors = wer(script_text, heard)
    detail = f"WER {rate:.1%} ({errors} word errors) between script and final mix"
    if rate > 0.15:
        return fail("speech.wer", "speech", detail, "voice", wer=rate)
    if rate > 0.08:
        return warn("speech.wer", "speech", detail, "voice", wer=rate)
    return ok("speech.wer", "speech", detail, wer=rate)


SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)")


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        for i, ln in enumerate(lines):
            m = SRT_TIME.search(ln)
            if m:
                g = [int(x) for x in m.groups()]
                start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                cues.append((start, end, " ".join(lines[i + 1:])))
                break
    return cues


def check_subtitle_sync(cues: list[tuple[float, float, str]],
                        words: list[tuple[str, float, float]]) -> Check:
    """Median offset between each cue's start and when its first word is actually heard."""
    heard = [(normalize_words(w)[0], s) for w, s, _ in words if normalize_words(w)]
    drifts = []
    for start, _, text in cues:
        first = normalize_words(text)
        if not first:
            continue
        near = [s for w, s in heard if w == first[0] and abs(s - start) <= 3.0]
        if near:
            drifts.append(start - min(near, key=lambda s: abs(s - start)))
    if len(drifts) < max(3, len(cues) // 3):
        return warn("subtitles.sync", "subtitles", f"only {len(drifts)}/{len(cues)} cues could "
                    f"be matched to speech", "timing")
    d = median(drifts)
    detail = f"median subtitle offset {d * 1000:+.0f} ms over {len(drifts)} cues"
    if abs(d) > 0.5:
        return fail("subtitles.sync", "subtitles", detail, "timing", median_s=d)
    if abs(d) > 0.25:
        return warn("subtitles.sync", "subtitles", detail, "timing", median_s=d)
    return ok("subtitles.sync", "subtitles", detail, median_s=d)


def check_subtitle_text(cues: list[tuple[float, float, str]], script_text: str) -> Check:
    same = normalize_words(" ".join(t for _, _, t in cues)) == normalize_words(script_text)
    return (ok("subtitles.text", "subtitles", "subtitle text matches the script") if same else
            fail("subtitles.text", "subtitles", "subtitle text differs from the script",
                 "subtitles"))
