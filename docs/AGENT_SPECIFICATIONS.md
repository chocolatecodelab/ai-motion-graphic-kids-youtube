# Agent Specifications

Every agent is a stage module in `src/factory/agents/<name>.py` exposing:

```python
class Agent(Protocol):
    name: str
    version: str                      # bump on prompt/schema change → invalidates cache
    tier: Literal["reasoning", "standard", "fast", "none"]
    Input: type[BaseModel]
    Output: type[BaseModel]
    def run(self, inp: Input, ctx: StageContext) -> Output: ...
    def validate(self, out: Output, ctx: StageContext) -> list[ValidationIssue]: ...
```

`StageContext` provides: providers (metered), storage, brand/character context (prompt-cached), budget guard and logger.

All LLM outputs use structured JSON (`output_config.format`) generated from the Pydantic `Output`. Validation is deterministic code. An LLM never grades its own output in the same call.

Shared context is prompt-cached (stable prefix order: system → brand guide → Character Bible → format template → per-episode data last):
- Brand Guide
- Character Bible (current `character_version`)
- Kids Safety Policy
- Storytelling Framework

---

## 1. Research Agent (`research`, tier: standard)
- **Does:** generates candidate topics per pillar mix, finds reliable sources, and writes topic briefs.
- **Tools:**
  - Claude `web_search` with `allowed_domains` = trusted-source allowlist (`config/sources.yaml`);
  - `web_fetch` with citations;
  - catalogue lookup (published or scheduled topics);
  - analytics insights digest.
- **Output (per candidate):** `title, central_question, pillar, target_age, learning_objective, interesting_facts[{text, source_ids}], sources[{url, title, publisher, tier, quote}], storytelling_angle, twist_candidate, est_complexity(1–5), visual_opportunities[]`.
- **Rules:**
  - Facts without a fetched quote are dropped.
  - No sources outside the allowlist count toward reliability. Wikipedia is used for discovery only.
  - Prefers evergreen topics.
- **Cost control:** max 25 searches per run; Batch API when run nightly.

## 2. Topic Selection Agent (`topic_select`, tier: fast + code)
- **Does:** scores candidates (rubric in content-opportunity-analysis.md), applies hard gates and dedupes against the catalogue (embedding similarity).
- **Output:** `ranked[{topic_id, scores{…}, total, rationale}], recommended_topic_id, rejected[{topic_id, reason}]`.
- **Rules:** never select on trendiness alone. Pillar rotation: no more than 2 consecutive episodes from the same pillar.

## 3. Fact-Checking Agent (`fact_check`, tier: fast for extraction, reasoning for adjudication)
- **Does:**
  1. extracts atomic claims from the brief (and later from the script, in `script_validate`);
  2. matches each claim to source quotes;
  3. fetches additional sources if there are fewer than 2 independent ones;
  4. adjudicates each claim.
- **Output:** `claims[{id, text, category, status: supported|partially_supported|unsupported|contradicted|opinion, confidence, evidence[{source_id, quote}], correction, simplification_note}] , verdict`.
- **Rules:**
  - Never invent citations. A quote must be a verbatim substring of the stored snapshot, and code verifies this.
  - Kid-level simplifications are allowed only when flagged as `simplification_note` and not false ("simplified but true").
  - Numeric claims need an exact source number or a range.
  - Any `unsupported` or `contradicted` key claim makes the verdict `fail`.

## 4. Scriptwriting Agent (`script`, tier: reasoning)
- **Does:** writes the episode following HOOK → MYSTERY → ADVENTURE → DISCOVERY → TWIST → TAKEAWAY, with the hero (plus the optional compass companion) as protagonist.
- **Input:** brief + verified claims only (by ID) + Character Bible + format template + "avoid list" (recent episodes' jokes and analogies).
- **Output:**
  `title_working, learning_objectives[], est_duration_s, scenes[{key, beat, location, summary, lines[{speaker, text, emotion, claim_ids[], direction}], sound_cues[], visual_opportunities[]}]`.
- **Validation (code):**
  - hook question within the first 15 s (≤ 40 words before the question);
  - word count in range;
  - Flesch–Kincaid grade ≤ 6.5 and average sentence ≤ 14 words;
  - every factual line cites claim IDs that exist and passed;
  - banned-pattern list (generic AI phrasing such as "Let's dive in", "In today's video", unnecessary intros);
  - no instructions for unsafe experiments without a safety line.

## 5. Storyboard Agent (`storyboard`, tier: standard)
- **Does:** converts the approved script to the machine-readable storyboard (`schemas/storyboard.schema.json`).
- **Scene fields:**
  `scene_id, objective, beat, duration_s, character_action{rig_pose, expression, action_id}, dialogue[{line_id, speaker}], voice_over[line_id], background{asset_request|library_id, parallax_layers}, camera{move: static|push_in|pan|parallax|orbit, from, to, easing}, animation[{component, props}], visual_assets[], motion_graphics[{component: Timeline|BarGrow|Orbit|Counter|Label|ExplodedView|Cutaway|ScaleCompare, props}], sfx[{id, at_line|t}], transition{type: compass_portal|wipe|cut|zoom_through, duration_s}, educational_purpose`.
- **Rules:** may only use components in the component catalogue and rig IDs in the rig contract. Unknown IDs fail validation.

## 6. Visual Director Agent (`visual_plan`, tier: standard)
- **Does:**
  - resolves each scene's visual needs to *reuse* (asset-library search by tags/embedding) or *generate*;
  - writes image prompts following the Visual Style Guide;
  - attaches style reference images;
  - defines composition: rule-of-thirds slot for the character, text-safe areas.
- **Output:** `asset_requests[{request_id, kind, reuse_asset_id|null, prompt, style_refs[], size, alpha, layers}]`, per-scene layout.
- **Rules:**
  - never requests images of the hero character (rig only);
  - palette from brand tokens;
  - no text baked into generated images. All text is rendered by Remotion, so it stays readable and editable.

## 7. Asset Generation Agent (`assets`, tier: none + vision check)
- **Does:** executes asset requests through `ImageProvider`, post-processes them (background removal for props, parallax splitting, resize), and stores them with provenance and licence.
- **Validation:**
  - format and dimensions;
  - alpha present where required;
  - vision check (cheap model) for style conformity, absence of text artefacts and kid safety;
  - perceptual-hash dedupe.
- Up to 3 regeneration attempts, then flag for human review.

## 8. Voice Production Agent (`voice`, tier: none)
- **Does:**
  - TTS per line with the speaker's voice settings and emotion/pacing tags;
  - pronunciation lexicon;
  - timestamps (provider or WhisperX alignment);
  - viseme track generation;
  - subtitle files.
- **Validation:** per-line STT WER ≤ 5%, duration sanity, no clipping, consistent loudness per line (normalised before mix).

## 9. Animation & Video Production Agent (`timing` → `render_scenes` → `audio_mix` → `assemble`, tier: none)
- Deterministic code.
- Builds the frame-accurate render plan, renders scenes through the Remotion render server (scene-level cache), mixes audio (ducking), concatenates and encodes.
- Supports preview (540p) vs final (1080p; 4K later), configurable fps, and per-scene re-render.

## 10. Quality Assurance Agent (`qa`, tier: code + standard/reasoning for review)
- **Automated technical checks:**
  - ffprobe spec;
  - `blackdetect`, `freezedetect`, `silencedetect`;
  - EBU R128 loudness and true peak;
  - A/V duration drift;
  - corrupted-frame decode test (`ffmpeg -v error -f null`).
- **Deterministic content checks:**
  - text contrast and size come from render-plan data (WCAG contrast ≥ 4.5:1, min text height);
  - subtitle WER (STT of the final mix vs script);
  - every claim in the script is still in the passed set.
- **AI-assisted review:**
  - Frames are sampled every N seconds plus each scene's mid-frame. A vision model compares them against the character reference sheet for on-model identity, rendering glitches and composition.
  - A reasoning model reviews script + transcript for clarity, age appropriateness, pacing, hook and ending quality.
- **Output:** `score, verdict, critical_errors[], warnings[], suggestions[], per_dimension{educational, storytelling, visual, audio, technical}`.
- **Policy:** the report states that AI inspection reduces risk but does not guarantee accuracy. Critical errors always block, and in APPROVAL_REQUIRED mode a human sees the report.

## 11. Thumbnail & SEO Agent (`thumbnail_seo`, tier: standard + image)
- **Output:**
  - 3 thumbnail concepts (hero pose from the rig + generated discovery object + ≤ 3 words);
  - 5 title options (question form, ≤ 60 chars, no clickbait);
  - description (summary, learning objectives, **sources list**, AI-assistance disclosure line);
  - chapters (from scene beats);
  - tags.
- **Validation:**
  - legibility test at 168×94 (OCR the downscaled image);
  - title–thumbnail–video consistency check;
  - a "misleading claim" check against the fact-check report.

## 12. YouTube Publishing Agent (`upload`, `schedule_publish`, `verify_publication`, tier: none)
- Resumable upload via `google-api-python-client` `MediaFileUpload(resumable=True)`.
- Sets `snippet` (title, description, tags, categoryId=27, defaultLanguage/defaultAudioLanguage=en) and `status` (privacyStatus=private, publishAt, selfDeclaredMadeForKids=true, containsSyntheticMedia per policy decision).
- Then `thumbnails.set` and `captions.insert`, followed by a re-read verification.
- Persists the session URI for resume. Never logs tokens. Mode-gated.

## 13. Analytics Agent (`analytics`, tier: standard for insights)
- Pulls Analytics API metrics on d1/d7/d28 and Reporting API reach (impressions, CTR) when available.
- Maps retention to scene timings and produces `insights{topic_signals, scene_dropoff_patterns, thumbnail_style_ctr, recommendations}`, which feed the Research and Topic Selection agents.
- **Guardrail:** recommendations are scored on a composite of retention, QA educational score and views, never on views alone.
