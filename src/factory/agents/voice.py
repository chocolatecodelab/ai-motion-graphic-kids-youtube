"""`voice` stage: synthesize every script line with the character's Kokoro voice.

Per line: TTS -> loudness-normalise -> WAV (+ word timestamps) -> local STT check.
Lines are cached by (engine, model, voice, speed, text), so re-runs after a script
edit only synthesize the lines that changed.

Blocking checks: silent/empty audio, overall WER above the limit, total speech
outside the target duration. Per-line WER spikes and duration drift are warnings.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from factory.agents.common import content_dir, load_upstream, save
from factory.artifacts import write_text
from factory.db.models import Lane
from factory.media import audio as A
from factory.media.stt import Transcriber, WhisperTranscriber, normalize_words, wer
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.providers.tts import TTSProvider, get_tts
from factory.providers.tts.kokoro import load_lexicon
from factory.resources import sha256_text
from factory.schemas.brief import TopicBrief
from factory.schemas.script import Script
from factory.schemas.voice import VoiceLine, VoiceManifest, Word

GAP_S = 0.35
MAX_OVERALL_WER = 0.05
LINE_WER_WARN = 0.20
DURATION_DRIFT_WARN = 0.25
DURATION_TOLERANCE = 0.10


def voice_for(speaker: str, ctx: StageContext) -> tuple[str, float]:
    s = ctx.settings
    if speaker == "needle":
        return s.tts_companion_voice, s.tts_companion_speed
    return s.tts_hero_voice, s.tts_hero_speed


class VoiceStage(Stage):
    name = "voice"
    lane = Lane.MEDIA
    version = "1"
    depends_on = ("brief", "script", "script_validate")
    max_attempts = 2

    def __init__(self, tts: TTSProvider | None = None, stt: Transcriber | None = None):
        self._tts = tts
        self._stt = stt

    def tts(self, ctx: StageContext) -> TTSProvider:
        if self._tts is None:
            self._tts = get_tts(ctx.settings)
        return self._tts

    def stt(self) -> Transcriber:
        if self._stt is None:
            self._stt = WhisperTranscriber()
        return self._stt

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        s = ctx.settings
        return {"script": ctx.upstream["script"]["sha256"],
                "voices": [s.tts_provider, s.tts_hero_voice, s.tts_hero_speed,
                           s.tts_companion_voice, s.tts_companion_speed],
                "lexicon": sha256_text(json.dumps(load_lexicon(), sort_keys=True))}

    def run(self, ctx: StageContext) -> StageResult:
        brief = load_upstream(ctx, "brief", TopicBrief)
        script = load_upstream(ctx, "script", Script)
        tts, stt = self.tts(ctx), self.stt()
        cdir = content_dir(ctx)
        lines_dir = ctx.workdir / "lines"
        cache_dir = Path(ctx.settings.library_dir) / "cache" / "tts"
        hint = "Kai, Needle. " + ", ".join(sorted(load_lexicon()))

        out_lines: list[VoiceLine] = []
        preview: list[np.ndarray] = []
        sample_rate = 0
        cursor = 0.0
        for ln in script.lines:
            voice, speed = voice_for(ln.speaker, ctx)
            if not voice:
                raise PermanentStageError(f"no voice configured for {ln.speaker}")
            key = hashlib.sha256(json.dumps(
                [tts.info.engine, tts.info.model, voice, speed, ln.text,
                 sorted(load_lexicon().items())]).encode()).hexdigest()
            audio, sr, words, cached = self._synth(tts, cache_dir, key, ln.text, voice, speed)
            sample_rate = sample_rate or sr
            if sr != sample_rate:
                raise PermanentStageError(f"sample rate changed mid-episode ({sr})")
            if audio.size == 0 or A.dbfs(A.rms(audio)) < A.SILENCE_RMS_DBFS:
                raise PermanentStageError(f"{ln.line_id}: TTS produced silent audio")
            audio = A.normalize(audio)
            path = lines_dir / f"{ln.line_id}.wav"
            A.write_wav(path, audio, sr)
            data = path.read_bytes()
            duration = round(audio.size / sr, 3)

            heard = stt.transcribe(path, hint=hint)
            rate, errors = wer(ln.text, heard)
            warnings = []
            if rate > LINE_WER_WARN and errors >= 2:
                warnings.append(f"STT heard {heard!r} (WER {rate:.0%}). Check pronunciation; "
                                f"add a lexicon entry if needed.")
            if ln.est_duration_s and abs(duration - ln.est_duration_s) / ln.est_duration_s > \
                    DURATION_DRIFT_WARN:
                warnings.append(f"duration {duration:.1f}s vs estimate "
                                f"{ln.est_duration_s:.1f}s")
            out_lines.append(VoiceLine(
                line_id=ln.line_id, speaker=ln.speaker, text=ln.text, voice=voice, speed=speed,
                file=path.resolve().relative_to(cdir.resolve()).as_posix(),
                sha256=hashlib.sha256(data).hexdigest(), duration_s=duration,
                est_duration_s=ln.est_duration_s, preview_start_s=round(cursor, 3),
                words=[Word(text=w.text, start=w.start, end=w.end) for w in words],
                stt_text=heard, wer=round(rate, 4), word_errors=errors,
                peak_dbfs=round(A.dbfs(A.peak(audio)), 2), rms_dbfs=round(A.dbfs(A.rms(audio)), 2),
                cached=cached, warnings=warnings,
            ))
            preview += [audio, A.silence(GAP_S, sr)]
            cursor += duration + GAP_S

        total_words = sum(len(normalize_words(ln.text)) for ln in script.lines) or 1
        overall = sum(v.word_errors for v in out_lines) / total_words
        speech = round(sum(v.duration_s for v in out_lines), 2)
        preview_path = ctx.workdir / "vo_preview.wav"
        A.write_wav(preview_path, np.concatenate(preview), sample_rate)

        problems = []
        if overall > MAX_OVERALL_WER:
            problems.append(f"overall WER {overall:.1%} exceeds {MAX_OVERALL_WER:.0%}")
        lo = brief.duration.min_s * (1 - DURATION_TOLERANCE) - GAP_S * len(out_lines)
        hi = brief.duration.max_s * (1 + DURATION_TOLERANCE)
        if not lo <= speech <= hi:
            problems.append(f"total speech {speech:.0f}s outside {lo:.0f}-{hi:.0f}s")

        manifest = VoiceManifest(
            episode_slug=script.episode_slug, script_version=script.version,
            sample_rate=sample_rate, engine=tts.info.engine, model=tts.info.model,
            licence=tts.info.license, stt_model=getattr(stt, "model_name", "unknown"),
            gap_s=GAP_S, lines=out_lines,
            preview_file=preview_path.resolve().relative_to(cdir.resolve()).as_posix(),
            total_speech_s=speech, preview_duration_s=round(cursor, 2),
            overall_wer=round(overall, 4),
            warnings=[f"{v.line_id}: {w}" for v in out_lines for w in v.warnings],
        )
        ref = save(ctx, "manifest", manifest)
        report = write_text(cdir, ctx.workdir / f"voice_report.v{ref['version']}.md",
                            voice_report(manifest))
        if problems:
            raise PermanentStageError("voice checks failed: " + "; ".join(problems)
                                      + f" (report: {report})")
        return StageResult({**ref, "preview": manifest.preview_file, "report": report,
                            "lines": len(out_lines), "speech_s": speech,
                            "overall_wer": manifest.overall_wer,
                            "warnings": len(manifest.warnings),
                            "cached_lines": sum(v.cached for v in out_lines)})

    @staticmethod
    def _synth(tts: TTSProvider, cache_dir: Path, key: str, text: str, voice: str,
               speed: float):  # type: ignore[no-untyped-def]
        wav, meta = cache_dir / f"{key}.wav", cache_dir / f"{key}.json"
        if wav.exists() and meta.exists():
            audio, sr = A.read_wav(wav)
            words = [Word(**w) for w in json.loads(meta.read_text(encoding="utf-8"))]
            return audio, sr, words, True
        result = tts.synthesize(text, voice, speed)
        A.write_wav(wav, result.audio, result.sample_rate)
        meta.write_text(json.dumps([w.__dict__ for w in result.words]), encoding="utf-8")
        audio, sr = A.read_wav(wav)  # same 16-bit quantisation as the cached path
        return audio, sr, [Word(text=w.text, start=w.start, end=w.end)
                           for w in result.words], False


def voice_report(m: VoiceManifest) -> str:
    out = [f"# Voice report: {m.episode_slug}", "",
           f"{m.engine} ({m.model}, {m.licence}) · STT {m.stt_model} · "
           f"speech {m.total_speech_s:.0f}s · preview {m.preview_duration_s:.0f}s · "
           f"overall WER {m.overall_wer:.1%}", "",
           "| line | speaker | voice | dur | est | WER | heard |", "|---|---|---|---|---|---|---|"]
    for v in m.lines:
        flag = " ⚠" if v.warnings else ""
        out.append(f"| {v.line_id}{flag} | {v.speaker} | {v.voice}@{v.speed:g} | "
                   f"{v.duration_s:.1f}s | {v.est_duration_s:.1f}s | {v.wer:.0%} | "
                   f"{v.stt_text.replace('|', '/')} |")
    if m.warnings:
        out += ["", "## Warnings", *[f"- {w}" for w in m.warnings]]
    return "\n".join(out) + "\n"
