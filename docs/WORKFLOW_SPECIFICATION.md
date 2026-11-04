# Workflow Specification: Daily Episode Pipeline (workflow v1)

## Stage table
Every stage records its outputs, a status, an input hash and its cost. Approval gates depend on `publication_mode`:
- **M** = MANUAL
- **A** = APPROVAL_REQUIRED (the default)
- **F** = FULL_AUTOMATION

| # | Stage | Lane | Inputs | Outputs | Validation (fail → status) | Retry | Gate |
|---|---|---|---|---|---|---|---|
| 0 | `schedule_slot` | — | publishing_schedules | episode row (planned) for the slot ≥ N days ahead | No existing episode in the slot | — | — |
| 1 | `research` | llm | Pillar mix, analytics insights, catalogue | ≥5 `content_topics` candidates + topic briefs + sources | Each brief schema-valid; ≥2 sources each | 3 | — |
| 2 | `topic_select` | llm | Candidates, catalogue embeddings | Ranked list, selected topic | Hard gates (safety, duplicate, sources) | 2 | M/A: optional owner pick from top 3 (timeout → auto top-1) |
| 3 | `fact_check` | llm | Topic brief, sources | Fact-check report + claims | Verdict pass; zero unsupported key claims | 2 | — (failure → back to 2 with the next topic) |
| 4 | `script` | llm | Brief, verified claims, Character Bible, brand guide, format template | script.vN.json/.md | Schema; beats present; 750–1,100 words; readability grade ≤ 6.5; only verified claims referenced (claim IDs) | 2 | — |
| 5 | `script_validate` | llm | Script, claims | Validation report | Safety rubric; claim coverage; no new facts; similarity vs catalogue < threshold | — | **A: owner approves script** · F: rubric score ≥ threshold |
| 6 | `storyboard` | llm | Approved script, rig contract, component catalogue | storyboard.vN.json | JSON Schema; every scene uses known components and rig IDs; durations sum to target ± 10% | 2 | — |
| 7 | `visual_plan` | llm | Storyboard, asset library index, style guide | Asset requests (reuse or generate), prompts, layouts | Every asset request is resolvable; style refs attached | 2 | — |
| 8 | `assets` | media | Asset requests | visual_assets (+ provenance, licence) | Dimensions, format, alpha where needed, NSFW/safety screen, vision check vs style | 3 per asset | — |
| 9 | `voice` | media | Script lines, voice settings, lexicon | VO line files + timestamps | Duration within ±15% of estimate; per-line WER ≤ 5% (local STT) | 3 per line | — |
| 10 | `subtitles` | media | VO timestamps, script text | en.srt / en.vtt | Line length ≤ 42 chars, ≤ 2 lines, min duration 1 s, text == script | 1 | — |
| 11 | `timing` | media | Storyboard, VO durations | Render plan (frame-accurate), viseme tracks | No overlaps; scene durations ≥ VO | 1 | — |
| 12 | `render_scenes` | render | Render plan, assets | Scene renders (cached by hash) + stills | Remotion exit 0; frames == expected | 2 per scene | (A: optional storyboard-stills approval before full render; off by default) |
| 13 | `audio_mix` | media | VO, music, SFX cues | mix.wav | −14 LUFS ±1, TP ≤ −1 dBTP, VO intelligibility (ducking) | 2 | — |
| 14 | `assemble` | media | Scene renders, mix, captions | episode.vN.mp4 | ffprobe: 1920×1080, 30 fps, H.264/AAC, duration in range | 2 | — |
| 15 | `qa` | llm+media | Final video, script, claims, rig refs | qa-report | No critical errors; score ≥ 80 | — | Fail → route to the responsible stage with the reason |
| 16 | `thumbnail_seo` | llm+media | Script, key frames, brand | Thumbnails, titles, description (with sources), chapters, tags | Metadata gate; thumbnail legibility at 168×94 | 2 | — |
| 17 | `final_approval` | — | Everything | approval row | — | — | **M: stop here (manual upload package)** · **A: owner approves final video** · F: automated gate |
| 18 | `upload` | publish | MP4, metadata, thumbnail, captions | youtube_videos row (private) | Upload complete; processing done; thumbnail + captions set | 5 (resumable) | — |
| 19 | `schedule_publish` | publish | Video ID, planned slot | `publishAt` set | Re-read resource matches | 3 | A: after explicit publish approval (may be combined with 17) |
| 20 | `verify_publication` | publish | Video ID | Status verified post-publish time | Public at the expected time | 3 (hourly) | — |
| 21 | `analytics` | llm | Video IDs (d1, d7, d28) | analytics_snapshots + insights | API responses valid | 3 | — |

## Job state machine
```
pending ──deps met──► queued ──claimed──► running ──► succeeded
                                     │            └─► awaiting_approval ──approve──► succeeded
                                     │                                   └─reject──► (new revision of the target stage)
                                     ├─► failed_retryable ──backoff──► queued   (attempt < max)
                                     ├─► failed_permanent  (validation fail / attempts exhausted / 4xx)
                                     └─► cancelled
```
- Backoff: `min(2^attempt × 30 s, 30 min) + jitter`.
- `failed_permanent` raises an alert and leaves the episode in `failed`, recoverable via dashboard **Retry stage**. Retry reuses all succeeded upstream outputs.
- QA failure routing:
  - bad VO line → `voice` (that line only);
  - bad asset → `assets` (that asset) → re-render the affected scenes;
  - factual issue → `script`;
  - technical issue → `assemble` / `render_scenes`.

## Timeline (default, configurable; Asia/Jakarta)
- Topic research runs **3 days ahead** of the slot (buffer for approvals and failures).
- 02:00: `research` + `topic_select` for slot D+3 (Batch API eligible).
- 03:00–06:00: content stages for D+2 (script ready for owner review in the morning).
- After script approval: production stages run immediately (about 1–2 h).
- Final approval by the owner: same or next day. `upload` then runs immediately as private, with `publishAt` = slot time.
- Publication slot: initially a fixed local time, chosen later from audience analytics (global audience → test 2–3 windows).
- Buffer policy: target **≥2 approved, scheduled episodes in the queue** before enabling daily cadence.

## Duplicate & concurrency protections
- One active workflow per episode (advisory lock on `episode_id`).
- Topic uniqueness: DB unique constraint + embedding similarity < 0.85 vs the catalogue.
- Upload idempotency: before `videos.insert`, check `youtube_videos` for the episode. A resumable session URI is persisted, so a crash resumes the same upload rather than starting a new one.
- Daily slot: unique partial index (see DATABASE_SCHEMA.md).

## Manual intervention points (dashboard)
Pause/cancel an episode, retry a stage, edit the script (creates a new version, so downstream stages re-run), swap the topic, replace an asset, re-voice a line, re-render a scene, override a QA warning (never a critical error), and change the slot.
