"""`subtitles` stage: SRT + WebVTT from the voice manifest.

Cue text always comes from the script (so subtitles == script). Timing comes from
the TTS word timestamps. Rules (WORKFLOW_SPECIFICATION stage 10): <= 42 characters
per line, <= 2 lines, >= 1 s on screen, one speaker per cue. Reading speed above
17 characters/s is a warning.

Times are on the vo_preview timeline. The timing stage shifts them onto the
final cut once scene timings are fixed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from factory.agents.common import content_dir, load_upstream, save
from factory.artifacts import write_text
from factory.db.models import Lane
from factory.media.stt import normalize_words
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.schemas.voice import Cue, Subtitles, VoiceLine, VoiceManifest

MAX_LINE = 42
MAX_LINES = 2
MAX_CUE_S = 6.0
MIN_CUE_S = 1.0
MAX_CPS = 17.0
_SENTENCE_END = re.compile(r"[.!?…]['\"]?$")


def timed_words(line: VoiceLine) -> list[tuple[str, float, float]]:
    """Script words (punctuation attached) with absolute times on the preview timeline."""
    words = line.text.split()
    spoken = [w for w in line.words if re.search(r"\w", w.text)]
    base = line.preview_start_s
    if len(spoken) == len(words) and spoken:
        return [(w, base + t.start, base + t.end) for w, t in zip(words, spoken, strict=True)]
    # Fallback: spread words over the clip proportionally to their length.
    total = sum(len(w) for w in words) or 1
    out, t = [], base
    for w in words:
        d = line.duration_s * len(w) / total
        out.append((w, t, t + d))
        t += d
    return out


def split_lines(text: str) -> list[str]:
    if len(text) <= MAX_LINE:
        return [text]
    words = text.split()
    best: tuple[int, list[str]] | None = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) <= MAX_LINE and len(b) <= MAX_LINE:
            score = abs(len(a) - len(b))
            if best is None or score < best[0]:
                best = (score, [a, b])
    if best is None:
        raise ValueError(f"cannot fit cue into {MAX_LINES} lines: {text!r}")
    return best[1]


def _flush(cues: list[Cue], words: list[tuple[str, float, float]], line: VoiceLine) -> None:
    if words:
        text = " ".join(w for w, _, _ in words)
        cues.append(Cue(index=len(cues) + 1, start=words[0][1], end=words[-1][2],
                        speaker=line.speaker, line_id=line.line_id, lines=split_lines(text)))
        words.clear()


def build_cues(manifest: VoiceManifest) -> list[Cue]:
    cues: list[Cue] = []
    for line in manifest.lines:
        current: list[tuple[str, float, float]] = []
        for word in timed_words(line):
            candidate = " ".join([*(w for w, _, _ in current), word[0]])
            too_long = len(candidate) > MAX_LINE * MAX_LINES
            too_slow = bool(current) and word[2] - current[0][1] > MAX_CUE_S
            if current and (too_long or too_slow):
                _flush(cues, current, line)
            current.append(word)
            text_so_far = " ".join(w for w, _, _ in current)
            if _SENTENCE_END.search(word[0]) and len(text_so_far) >= 24:
                _flush(cues, current, line)
        _flush(cues, current, line)

    for i, cue in enumerate(cues):  # minimum duration, never overlapping the next cue
        if cue.end - cue.start < MIN_CUE_S:
            limit = cues[i + 1].start if i + 1 < len(cues) else cue.start + MIN_CUE_S
            cue.end = round(min(cue.start + MIN_CUE_S, max(limit, cue.end)), 3)
        cue.start, cue.end = round(cue.start, 3), round(cue.end, 3)
    return cues


def _ts(seconds: float, sep: str) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    return "\n".join(f"{c.index}\n{_ts(c.start, ',')} --> {_ts(c.end, ',')}\n"
                     + "\n".join(c.lines) + "\n" for c in cues)


def to_vtt(cues: list[Cue]) -> str:
    body = "\n".join(f"{_ts(c.start, '.')} --> {_ts(c.end, '.')}\n<v {c.speaker.title()}>"
                     + "\n".join(c.lines) + "\n" for c in cues)
    return "WEBVTT\n\n" + body


class SubtitlesStage(Stage):
    name = "subtitles"
    lane = Lane.MEDIA
    version = "1"
    depends_on = ("voice",)
    max_attempts = 1

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        return {"voice": ctx.upstream["voice"]["sha256"]}

    def run(self, ctx: StageContext) -> StageResult:
        manifest = load_upstream(ctx, "voice", VoiceManifest)
        try:
            cues = build_cues(manifest)
        except ValueError as exc:
            raise PermanentStageError(str(exc)) from exc

        sub_words = normalize_words(" ".join(" ".join(c.lines) for c in cues))
        script_words = normalize_words(" ".join(v.text for v in manifest.lines))
        if sub_words != script_words:
            raise PermanentStageError("subtitle text does not match the script")
        warnings = []
        for c in cues:
            chars = sum(len(x) for x in c.lines)
            cps = chars / max(c.end - c.start, 0.01)
            if cps > MAX_CPS:
                warnings.append(f"cue {c.index} ({c.line_id}) reads at {cps:.0f} chars/s")
            if any(len(x) > MAX_LINE for x in c.lines):
                raise PermanentStageError(f"cue {c.index} has a line over {MAX_LINE} chars")

        cdir = content_dir(ctx)
        srt = write_text(cdir, ctx.workdir / "en.srt", to_srt(cues))
        vtt = write_text(cdir, ctx.workdir / "en.vtt", to_vtt(cues))
        subs = Subtitles(cues=cues, srt_file=srt, vtt_file=vtt, warnings=warnings)
        ref = save(ctx, "subtitles", subs)
        return StageResult({**ref, "srt": srt, "vtt": vtt, "cues": len(cues),
                            "warnings": len(warnings)})
