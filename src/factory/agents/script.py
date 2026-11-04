"""`script` stage: write the episode (Opus tier) and enforce code checks.

Code checks (docs/AGENT_SPECIFICATIONS.md §4): beats in order, hook question in
the opening, duration in range, readability, claim IDs, banned phrases, unsafe
instructions. Failed checks go back to the model as a revision, at most twice.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from factory import resources
from factory.agents.common import (
    claims_block,
    content_dir,
    latest_feedback,
    load_upstream,
    save,
)
from factory.artifacts import next_version, write_text
from factory.db.models import Lane
from factory.pipeline import PermanentStageError, Stage, StageContext, StageResult
from factory.providers.llm import LLMProvider, LLMRequest, Tier
from factory.schemas.brief import TopicBrief
from factory.schemas.script import BEAT_ORDER, LineRef, Script, ScriptDraft
from factory.text import (
    LINE_GAP_S,
    SAFETY_LINE,
    UNSAFE_HINTS,
    WORDS_PER_SECOND,
    banned_hits,
    est_line_duration,
    readability,
    word_count,
)

PROMPT, REVISE, REVIEW_REVISE = "script/v1", "script/revise_v1", "script/review_revise_v1"
MAX_REVISIONS = 2
MAX_FK_GRADE = 6.5
MAX_AVG_SENTENCE = 14.0
MAX_LINE_FK_GRADE = 10.0  # a single line may be harder than average, but not jargon-dense
MIN_WORDS_FOR_LINE_CHECK = 8  # short exclamations with one long word are fine
MAX_WORDS_BEFORE_HOOK = 40
DURATION_TOLERANCE = 0.10


def speed_for(speaker: str, ctx: StageContext) -> float:
    s = ctx.settings
    return s.tts_companion_speed if speaker == "needle" else s.tts_hero_speed


def build_script(draft: ScriptDraft, slug: str, version: int, ctx: StageContext) -> Script:
    lines: list[LineRef] = []
    for scene in draft.scenes:
        for i, line in enumerate(scene.lines, start=1):
            lines.append(LineRef(
                line_id=f"{scene.key}-L{i:02d}", scene_key=scene.key, speaker=line.speaker,
                text=line.text, emotion=line.emotion, claim_ids=line.claim_ids,
                direction=line.direction,
                est_duration_s=est_line_duration(line.text, speed_for(line.speaker, ctx)),
            ))
    texts = [ln.text for ln in lines]
    duration = round(sum(ln.est_duration_s for ln in lines) + LINE_GAP_S * len(lines), 1)
    return Script(
        episode_slug=slug, version=version, draft=draft, lines=lines,
        word_count=sum(word_count(t) for t in texts), est_duration_s=duration,
        readability=readability(texts).as_dict(),
    )


def check_script(script: Script, brief: TopicBrief) -> list[str]:
    issues: list[str] = []
    draft = script.draft

    keys = [s.key for s in draft.scenes]
    if keys != [f"S{i:02d}" for i in range(1, len(keys) + 1)]:
        issues.append(f"Scene keys must be S01, S02, ... in order (got {keys}).")
    beats = [s.beat for s in draft.scenes]
    order = [BEAT_ORDER.index(b) for b in beats]
    if order != sorted(order):
        issues.append(f"Beats must follow hook, mystery, adventure, discovery, twist, takeaway "
                      f"in order (got {beats}).")
    missing = [b for b in BEAT_ORDER if b not in beats]
    if missing:
        issues.append(f"Missing beats: {missing}.")

    before = 0
    for line in script.lines:
        if "?" in line.text:
            before += word_count(line.text.split("?")[0])
            break
        before += word_count(line.text)
    else:
        before = 10**6
    if before > MAX_WORDS_BEFORE_HOOK:
        issues.append(f"The central question must be asked within the first "
                      f"{MAX_WORDS_BEFORE_HOOK} spoken words (found after {before}).")

    lo = brief.duration.min_s * (1 - DURATION_TOLERANCE)
    hi = brief.duration.max_s * (1 + DURATION_TOLERANCE)
    if not lo <= script.est_duration_s <= hi:
        target_words = (int(brief.duration.min_s * WORDS_PER_SECOND * 0.85),
                        int(brief.duration.max_s * WORDS_PER_SECOND * 0.85))
        issues.append(f"Estimated spoken length is {script.est_duration_s:.0f}s "
                      f"({script.word_count} words); target {brief.duration.min_s}-"
                      f"{brief.duration.max_s}s, about {target_words[0]}-{target_words[1]} words.")

    r = script.readability
    if r["fk_grade"] > MAX_FK_GRADE:
        issues.append(f"Reading level is grade {r['fk_grade']:.1f}; keep it at or below "
                      f"{MAX_FK_GRADE}. Use shorter sentences and simpler words.")
    if r["avg_sentence_words"] > MAX_AVG_SENTENCE:
        issues.append(f"Average sentence is {r['avg_sentence_words']:.1f} words; "
                      f"keep it at or below {MAX_AVG_SENTENCE:.0f}.")

    usable = {c.id for c in brief.usable_claims()}
    all_text = " ".join(ln.text for ln in script.lines)
    for line in script.lines:
        lr = readability([line.text])
        if lr.words >= MIN_WORDS_FOR_LINE_CHECK and lr.fk_grade > MAX_LINE_FK_GRADE:
            issues.append(f"{line.line_id} is too complex for 8-12-year-olds "
                          f"(grade {lr.fk_grade:.1f}): {line.text!r}. Split it and use "
                          f"simpler words.")
        unknown = [c for c in line.claim_ids if c not in usable]
        if unknown:
            issues.append(f"{line.line_id} cites unknown or unverified claim IDs {unknown}.")
        hits = banned_hits(line.text)
        if hits:
            issues.append(f"{line.line_id} uses banned phrasing ({', '.join(hits)}): "
                          f"{line.text!r}")
    if UNSAFE_HINTS.search(all_text) and not SAFETY_LINE.search(all_text):
        issues.append("The script mentions an activity that needs an adult-supervision line.")
    if not any(ln.claim_ids for ln in script.lines):
        issues.append("No line cites any claim. Factual lines must list their claim IDs.")
    return issues


def markdown(script: Script, brief: TopicBrief) -> str:
    out = [f"# {script.draft.title_working}", "",
           f"*{brief.central_question}*  ·  ~{script.est_duration_s:.0f}s  ·  "
           f"{script.word_count} words  ·  grade {script.readability['fk_grade']:.1f}", "",
           "**Learning objectives:** " + "; ".join(script.draft.learning_objectives), ""]
    lines = {ln.line_id: ln for ln in script.lines}
    for scene in script.draft.scenes:
        out += [f"## {scene.key} · {scene.beat.upper()} · {scene.location}", f"_{scene.summary}_",
                ""]
        for i, _ in enumerate(scene.lines, start=1):
            ln = lines[f"{scene.key}-L{i:02d}"]
            claims = f" `[{', '.join(ln.claim_ids)}]`" if ln.claim_ids else ""
            direction = f" _({ln.direction})_" if ln.direction else ""
            out.append(f"- **{ln.speaker.upper()}** ({ln.emotion}){direction}: {ln.text}{claims}")
        if scene.visual_opportunities:
            out.append(f"\n  Visuals: {'; '.join(scene.visual_opportunities)}")
        if scene.sound_cues:
            out.append(f"  Sound: {'; '.join(scene.sound_cues)}")
        out.append("")
    if script.validation_warnings:
        out += ["## Remaining warnings", *[f"- {w}" for w in script.validation_warnings]]
    return "\n".join(out)


class ScriptStage(Stage):
    name = "script"
    lane = Lane.LLM
    version = "2"  # v2: rewrites from reviewer feedback
    depends_on = ("brief",)
    max_attempts = 2

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        fb_version, fb_text = latest_feedback(ctx, self.name)
        return {"brief": ctx.upstream["brief"]["sha256"],
                "resources": resources.resource_hash(PROMPT, REVISE, REVIEW_REVISE),
                "model": ctx.settings.llm_model_high,
                "speeds": [ctx.settings.tts_hero_speed, ctx.settings.tts_companion_speed],
                "feedback": [fb_version, resources.sha256_text(fb_text)]}

    def _review_revision(self, ctx: StageContext, prompt: str) -> str:
        """If a reviewer sent feedback and a previous script exists, ask for a rewrite."""
        fb_version, fb_text = latest_feedback(ctx, self.name)
        previous = next_version(ctx.workdir, "script") - 1
        if not fb_version or previous < 1:
            return prompt
        prev_path = ctx.workdir / f"script.v{previous}.json"
        prev = Script.model_validate_json(prev_path.read_text(encoding="utf-8"))
        return prompt + "\n\n" + resources.render(
            resources.prompt(REVIEW_REVISE), feedback=fb_text,
            draft=json.dumps(prev.draft.model_dump(), ensure_ascii=False))

    def run(self, ctx: StageContext) -> StageResult:
        brief = load_upstream(ctx, "brief", TopicBrief)
        system = resources.shared_context()
        prompt = resources.render(
            resources.prompt(PROMPT),
            central_question=brief.central_question, title=brief.title,
            learning_objectives="\n".join(f"  - {o}" for o in brief.learning_objectives),
            storytelling_angle=brief.storytelling_angle, twist=brief.twist or "(none)",
            min_s=brief.duration.min_s, max_s=brief.duration.max_s,
            min_words=int(brief.duration.min_s * WORDS_PER_SECOND * 0.85),
            max_words=int(brief.duration.max_s * WORDS_PER_SECOND * 0.85),
            claims=claims_block(brief),
        )
        prompt = self._review_revision(ctx, prompt)
        version = next_version(ctx.workdir, "script")
        draft = self._call(prompt, system, ctx)
        script = build_script(draft, brief.slug, version, ctx)
        issues = check_script(script, brief)
        revisions = 0
        while issues and revisions < MAX_REVISIONS:
            revisions += 1
            revise = resources.render(
                resources.prompt(REVISE),
                issues="\n".join(f"- {i}" for i in issues),
                draft=json.dumps(draft.model_dump(), ensure_ascii=False),
            )
            draft = self._call(prompt + "\n\n" + revise, system, ctx)
            script = build_script(draft, brief.slug, version, ctx)
            issues = check_script(script, brief)

        script = script.model_copy(update={"revisions_used": revisions})
        if issues:
            # Keep the failed draft for the owner to inspect, then stop.
            script = script.model_copy(update={"validation_warnings": issues})
            save(ctx, "script_failed", script)
            raise PermanentStageError(
                f"script still fails {len(issues)} check(s) after {revisions} revisions: "
                + " | ".join(issues[:5])
            )
        ref = save(ctx, "script", script)
        md = write_text(content_dir(ctx), ctx.workdir / f"script.v{ref['version']}.md",
                        markdown(script, brief))
        return StageResult({**ref, "markdown": md, "word_count": script.word_count,
                            "est_duration_s": script.est_duration_s,
                            "revisions": revisions})

    def _call(self, prompt: str, system: str, ctx: StageContext) -> ScriptDraft:
        resp = self.llm.complete(
            LLMRequest(prompt=prompt, system=system, schema=ScriptDraft, tier=Tier.HIGH,
                       agent="script"),
            record_usage=ctx.record_usage,
        )
        assert resp.data is not None
        return resp.data
