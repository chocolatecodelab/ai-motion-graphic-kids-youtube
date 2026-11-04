# Database Schema (PostgreSQL 16)

Conventions:
- `id` is a `uuid` PK (uuid7 for ordering).
- `created_at` and `updated_at` are `timestamptz` (default now).
- Statuses are Postgres enums or `text` with a CHECK constraint.
- Large agent outputs go in `jsonb`, with key fields promoted to columns for indexing.
- Files are never stored in the DB, only `storage_key` + `sha256` + `bytes` + `mime`.
- Soft-delete is used only where needed (`archived_at`).

## Entity map

```
channels 1─* projects 1─* episodes ─┬─* production_jobs 1─* agent_executions 1─* model_usage
                                    │
characters 1─* character_versions ──┤ (episode pins character_version)
                                    ├─1 content_topics ─* research_sources
                                    ├─* research_reports
                                    ├─* scripts (versions) ─1 storyboards (versions) ─* scenes
                                    ├─* visual_assets / audio_assets (via asset links; library assets shared)
                                    ├─* render_jobs
                                    ├─* qa_reports
                                    ├─* thumbnails
                                    ├─* approvals
                                    ├─1 youtube_videos ─* analytics_snapshots
                                    └─1 publishing_schedules
system_logs, budgets, settings, oauth_credentials (encrypted)
```

`episodes` is added beyond the brief's list as the central aggregate. The brief's `production_jobs` hang off it.

## Tables (key columns)

### channels
`id, name, youtube_channel_id (unique, nullable until linked), default_language ('en'), made_for_kids (bool, default true), timezone ('Asia/Jakarta'), publication_mode ('MANUAL'|'APPROVAL_REQUIRED'|'FULL_AUTOMATION', default 'APPROVAL_REQUIRED'), full_automation_enabled_at, full_automation_enabled_by, brand_tokens (jsonb)`

### projects
A series or format within a channel (Main Quest, Compass Glitch, Shorts).
`id, channel_id FK, name, format ('long'|'short'), target_duration_s_min, target_duration_s_max, template_id, active`

### characters / character_versions
- `characters`: `id, slug (unique), name, role ('hero'|'companion'), status ('concept'|'approved'|'retired')`
- `character_versions`: `id, character_id FK, version (int), bible (jsonb), rig_contract (jsonb), rig_type ('vector_puppet'|'pose_library_3d'|'three_glb'), reference_sheet_key, voice_provider, voice_id, voice_settings (jsonb), approved_at, approved_by`. Unique `(character_id, version)`.

### content_topics
`id, channel_id FK, title, central_question, pillar (enum 5), learning_objective, target_age_min (8), target_age_max (12), storytelling_angle, complexity (1–5), scores (jsonb: curiosity, educational, storytelling, visual, reliability, freshness, feasibility, total), status ('candidate'|'selected'|'rejected'|'used'), rejection_reason, embedding (vector, optional pgvector), slug (unique per channel)`
- Index `(channel_id, status)`.
- **Duplicate-prevention:** unique `(channel_id, slug)`, plus a semantic similarity check at selection time.

### episodes
`id, project_id FK, topic_id FK unique, number (int, unique per project), slug, character_version_id FK, workflow_version, status ('planned'|'in_production'|'awaiting_approval'|'qa_failed'|'ready'|'uploaded'|'scheduled'|'published'|'cancelled'|'failed'), planned_publish_at, storage_prefix, current_script_id, current_storyboard_id, final_render_id, total_cost_usd (numeric(10,4), maintained), cancelled_at`
- Index `(status)`, `(planned_publish_at)`.
- **Daily-slot uniqueness:** unique partial index on `(project_id, (planned_publish_at AT TIME ZONE tz)::date) WHERE status <> 'cancelled'`, which prevents two episodes in one daily slot.

### research_sources
`id, topic_id FK, url, domain, title, publisher, source_tier (1 = primary institution / peer-reviewed, 2 = reputable reference, 3 = other), retrieved_at, content_sha256, snapshot_key (stored text), http_status`. Unique `(topic_id, url)`.

### research_reports
`id, episode_id FK (nullable for candidate topics), topic_id FK, kind ('topic_brief'|'fact_check'), version, payload (jsonb), claims_total, claims_supported, claims_blocked, verdict ('pass'|'fail'), agent_execution_id FK`

### claims (child of the fact-check report; normalised for gating and audit)
`id, research_report_id FK, text, category ('scientific'|'historical'|'numeric'|'safety'), status ('supported'|'partially_supported'|'unsupported'|'contradicted'|'opinion'), confidence (0–1), correction, source_ids uuid[]`, plus `evidence (jsonb: [{source_id, quote}])`.

### scripts
`id, episode_id FK, version, parent_id (revision chain), payload (jsonb: scenes, narration, dialogue, sound cues, objectives), word_count, est_duration_s, readability (jsonb: FK grade, avg sentence length), status ('draft'|'validated'|'approved'|'rejected'), validation_errors (jsonb), approved_at, agent_execution_id`. Unique `(episode_id, version)`.

### storyboards / scenes
- `storyboards`: `id, episode_id, script_id FK, version, schema_version, payload (jsonb, full storyboard), status, approved_at`
- `scenes`: `id, storyboard_id FK, scene_key ('S01'…), order_index, duration_s, objective, beat ('hook'|'mystery'|'adventure'|'discovery'|'twist'|'takeaway'), spec (jsonb), render_hash`. Unique `(storyboard_id, scene_key)`.

### visual_assets / audio_assets
- `visual_assets`: `id, scope ('library'|'episode'), episode_id (nullable), kind ('background'|'parallax_layer'|'prop'|'diagram'|'character_pose'|'thumbnail'|'concept'), tags text[], storage_key, sha256, width, height, mime, provenance (jsonb: provider, model, prompt, negative, refs[], seed, params), licence_ref, licence_terms_version, cost_usd, qa_status ('pending'|'ok'|'rejected'), created_by_execution_id`
- `audio_assets`: `id, scope, episode_id, kind ('vo_line'|'vo_full'|'music_bed'|'sfx'|'mix'), character_version_id (vo), text (vo), timestamps_key (alignment json), duration_s, lufs, storage_key, sha256, provenance, licence_ref, cost_usd`
- `asset_links`: `episode_id, asset_id, asset_type, scene_key, role` (many-to-many reuse of library assets)
- Indexes: GIN on `tags`; `(scope, kind)`; unique `sha256` per scope.

### production_jobs
`id, episode_id FK, stage (text), stage_version, lane ('llm'|'media'|'render'|'publish'), status (see the state machine in WORKFLOW_SPECIFICATION.md), attempt, max_attempts, input_hash, output_refs (jsonb), error_class, error_message, run_after (timestamptz, backoff), locked_by, locked_at, started_at, finished_at, requires_approval (bool)`
- Indexes `(status, lane, run_after)` for claiming; `(episode_id, stage)`; `(stage, input_hash) WHERE status='succeeded'` for cache reuse.

### agent_executions
`id, job_id FK, agent ('research'|…|'analytics'), prompt_template_version, provider, model, input_ref, output_ref, status, duration_ms, tokens_in, tokens_out, cost_usd, error`

### model_usage
Metering, one row per external billable call.
`id, execution_id FK (nullable), episode_id FK (nullable), provider, model, operation ('messages'|'web_search'|'image'|'tts'|'upload'…), units (jsonb: input_tokens, output_tokens, cache_read, chars, images, seconds), cost_usd numeric(10,6), request_hash, latency_ms, created_at`
- Index `(created_at)`, `(episode_id)`, `(provider, created_at)`.

### render_jobs
`id, episode_id, scope ('scene'|'preview'|'full'|'short'), scene_key, props_hash, code_hash, resolution, fps, codec, status, output_key, duration_s, frames, render_ms, error`

### qa_reports
`id, episode_id, render_job_id, version, score (0–100), verdict ('pass'|'fail'), critical_count, checks (jsonb: [{id, category, severity, status, detail}]), ai_review (jsonb), report_key`

### approvals
`id, episode_id, gate ('script'|'storyboard'|'final'|'publish'), decision ('approved'|'rejected'), notes, decided_by, decided_at, target_id (script/storyboard/render id)`

### thumbnails
`id, episode_id, visual_asset_id, concept, text_overlay, selected (bool), qa (jsonb: legibility at 168×94, focal point, brand)`

### youtube_videos
`id, episode_id FK unique, youtube_video_id unique, upload_session_uri (resumable), privacy_status, publish_at, made_for_kids (bool), contains_synthetic_media (bool), category_id ('27'), title, description, tags text[], default_language, upload_status, processing_status, thumbnail_set (bool), captions_set (bool), verified_at, raw (jsonb last API resource)`
- **Duplicate-upload prevention:** unique `episode_id` + upload idempotency key, plus a check of the existing `youtube_video_id` before any `videos.insert`.

### publishing_schedules
`id, channel_id, cron / rules (jsonb: weekdays, local_time, tz), active, next_slot_at`

### analytics_snapshots
`id, youtube_video_id FK, captured_at, window ('d1'|'d7'|'d28'|'lifetime'), metrics (jsonb: views, minutes, avg_view_duration_s, avg_view_pct, subs_gained, likes, impressions, ctr), retention (jsonb: [[ratio, watchRatio]…])`. Unique `(youtube_video_id, window, captured_at::date)`.

### oauth_credentials
`id, channel_id, provider ('google'), scopes text[], refresh_token_enc bytea, access_token_enc, expires_at, last_refreshed_at`. Values are encrypted with a Fernet key from env and never logged.

### system_logs
`id, ts, level, logger, episode_id, job_id, event, data (jsonb, redacted)`. Partitioned monthly; 90-day retention for info level.

### budgets / settings
- `budgets`: `scope ('daily'|'monthly'|'episode'), soft_usd, hard_usd`
- `settings`: key/value jsonb for non-secret runtime config (schedule, providers per tier, feature flags)

## Key invariants (enforced in DB or service layer)
1. One topic is used by at most one episode (`episodes.topic_id` unique).
2. One episode has at most one YouTube video.
3. FULL_AUTOMATION can only be set if `full_automation_enabled_by` is not null (an explicit owner action) **and** the last N trial episodes passed QA.
4. `publish` stage cannot run unless:
   - the latest `qa_reports.verdict = 'pass'`;
   - all linked assets have a `licence_ref`;
   - the fact-check verdict is `pass`;
   - required metadata is present;
   - the mode-specific approval exists.
