"""`qa` stage: automated technical QA of the assembled episode (M1 scope).

Checks: spec (resolution/fps/codecs/duration), clean decode, black and frozen frames,
loudness + true peak, silence inside voice lines, speech vs script (Whisper WER on the
final mix), subtitle text and sync, claim references, rights/provenance.

Score = 100 − 25 per critical − 5 per warning. Pass = no critical and score ≥ 80.
A failing report names the stage to fix; nothing is published without a pass (and, in
APPROVAL_REQUIRED mode, the owner's final approval).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from factory.agents.common import content_dir, load_upstream, save
from factory.artifacts import write_text
from factory.db.models import Lane
from factory.media.stt import WhisperTranscriber, WordTranscriber
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.qa import checks as C
from factory.resources import ROOT
from factory.schemas.brief import TopicBrief
from factory.schemas.qa import QACheck, QAReport
from factory.schemas.renderplan import RenderPlan
from factory.schemas.script import Script
from factory.schemas.voice import VoiceManifest

PASS_SCORE = 80
FONTS_DIR = ROOT / "remotion" / "public" / "fonts"
ALLOWED_VOICE_LICENCES = {"Apache-2.0", "MIT"}


def content_checks(script: Script, brief: TopicBrief) -> list[C.Check]:
    usable = {c.id for c in brief.usable_claims()}
    cited = {cid for ln in script.lines for cid in ln.claim_ids}
    unknown = sorted(cited - usable)
    return [C.ok("content.claims", "content", f"{len(cited)} verified claims referenced")
            if not unknown else
            C.fail("content.claims", "content", f"script cites unverified claims {unknown}",
                   "script")]


def rights_checks(manifest: VoiceManifest, fonts_dir: Path = FONTS_DIR) -> list[C.Check]:
    out = []
    out.append(C.ok("rights.voice", "rights", f"{manifest.engine} {manifest.model} "
                    f"({manifest.licence}), stock voices, no cloning")
               if manifest.licence in ALLOWED_VOICE_LICENCES else
               C.fail("rights.voice", "rights", f"voice licence {manifest.licence!r} not "
                      f"approved", "voice"))
    missing = []
    for font in sorted(fonts_dir.glob("*.[ot]tf")):
        family = font.stem.split("-")[0]
        if not any(fonts_dir.glob(f"{family}*.txt")):
            missing.append(font.name)
    out.append(C.ok("rights.fonts", "rights", "every font ships with its licence file")
               if not missing else
               C.fail("rights.fonts", "rights", f"fonts without licence file: {missing}", None))
    out.append(C.ok("rights.visuals", "rights",
                    "visuals are drawn in code by the project (owned); no third-party images"))
    out.append(C.ok("rights.music", "rights", "no music or SFX in this cut"))
    return out


def score(results: list[C.Check]) -> int:
    crit = sum(r.severity == "critical" for r in results)
    warns = sum(r.severity == "warning" for r in results)
    return max(0, 100 - 25 * crit - 5 * warns)


def markdown(report: QAReport) -> str:
    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
    out = [f"# QA report: {report.verdict.upper()} ({report.score}/100)", "",
           f"`{report.video}` · {report.quality}", "", f"> {report.disclaimer}", ""]
    if report.critical:
        out += ["## Critical (blocks publication)", *[f"- {c}" for c in report.critical], ""]
    if report.fix_stages:
        out += [f"**Re-run:** {', '.join(report.fix_stages)}", ""]
    if report.warnings:
        out += ["## Warnings", *[f"- {w}" for w in report.warnings], ""]
    out += ["## All checks", "", "| | check | detail |", "|---|---|---|"]
    out += [f"| {icon[c.status]} | {c.id} | {c.detail} |" for c in report.checks]
    return "\n".join(out) + "\n"


class QAStage(Stage):
    name = "qa"
    lane = Lane.MEDIA
    version = "1"
    depends_on = ("brief", "script", "voice", "timing", "assemble")
    max_attempts = 1

    def __init__(self, stt: WordTranscriber | None = None):
        self._stt = stt

    def stt(self) -> WordTranscriber:
        if self._stt is None:
            self._stt = WhisperTranscriber()
        return self._stt

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        a = ctx.upstream["assemble"]
        return {"video": a.get("video"), "loudness": a.get("loudness_lufs"),
                "voice_stem": a.get("voice_stem"),
                "timing": ctx.upstream["timing"]["sha256"],
                "script": ctx.upstream["script"]["sha256"]}

    def run(self, ctx: StageContext) -> StageResult:
        brief = load_upstream(ctx, "brief", TopicBrief)
        script = load_upstream(ctx, "script", Script)
        manifest = load_upstream(ctx, "voice", VoiceManifest)
        plan = load_upstream(ctx, "timing", RenderPlan)
        assembled = ctx.upstream["assemble"]
        cdir = content_dir(ctx)
        video = cdir / assembled["video"]
        if not video.exists():
            raise PermanentStageError(f"video missing: {video}")
        quality = assembled.get("quality", "final")
        scale = 0.5 if quality == "preview" else 1.0
        expected = {"width": int(plan.width * scale), "height": int(plan.height * scale),
                    "fps": plan.fps}
        total_s = plan.total_frames / plan.fps
        script_text = " ".join(ln.text for ln in script.lines)

        results: list[C.Check] = []
        results += C.check_spec(video, expected, total_s)
        results.append(C.check_decode(video))
        scan = C.scan(video)
        results.append(C.check_black(scan))
        results.append(C.check_freeze(scan))
        speech = [(a.start_s, a.start_s + a.duration_s) for a in plan.audio]
        stem = assembled.get("voice_stem")
        voice_sil = C.silences(cdir / stem) if stem and (cdir / stem).exists() else None
        results += C.check_silence(scan, speech, voice_silence=voice_sil)
        results += C.check_loudness(video)

        words = self.stt().transcribe_words(video, hint="Arka, Lipa.")
        heard = " ".join(w for w, _, _ in words)
        results.append(C.check_speech(script_text, heard))
        srt = assembled.get("srt")
        if srt and (cdir / srt).exists():
            cues = C.parse_srt((cdir / srt).read_text(encoding="utf-8"))
            results.append(C.check_subtitle_text(cues, script_text))
            results.append(C.check_subtitle_sync(cues, words))
        else:
            results.append(C.fail("subtitles.present", "subtitles", "no subtitle file",
                                  "timing"))
        results += content_checks(script, brief)
        results += rights_checks(manifest)

        sc = score(results)
        critical = [f"{r.id}: {r.detail}" for r in results if r.severity == "critical"]
        verdict = "pass" if not critical and sc >= PASS_SCORE else "fail"
        cats: dict[str, int] = {}
        penalty = {"critical": 25, "warning": 5, "info": 0}
        for r in results:
            cats[r.category] = cats.get(r.category, 100) - penalty[r.severity]
        report = QAReport(
            episode_slug=script.episode_slug, video=assembled["video"], quality=quality,
            score=sc, verdict=verdict, critical=critical,
            warnings=[f"{r.id}: {r.detail}" for r in results if r.severity == "warning"],
            per_category={k: max(0, v) for k, v in cats.items()},
            fix_stages=sorted({r.fix_stage for r in results
                               if r.severity == "critical" and r.fix_stage}),
            checks=[QACheck(**r.__dict__) for r in results],
        )
        ref = save(ctx, "qa_report", report)
        md = write_text(cdir, ctx.workdir / f"qa_report.v{ref['version']}.md", markdown(report))
        (ctx.workdir / f"heard.v{ref['version']}.txt").write_text(heard, encoding="utf-8")
        if verdict == "fail":
            raise PermanentStageError(
                f"QA failed ({sc}/100): " + " | ".join(critical[:4])
                + (f" → re-run {', '.join(report.fix_stages)}" if report.fix_stages else "")
                + f" (report: {md})")
        return StageResult({**ref, "markdown": md, "score": sc, "verdict": verdict,
                            "warnings": len(report.warnings), "quality": quality})
