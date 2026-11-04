# System Architecture: AI Kids Educational Animation Factory

Status: Phase 1 proposal · for owner review.

## 1. Principles
1. **Deterministic pipeline, AI inside stages.** The orchestrator, rather than an LLM, decides what runs next. AI is used where judgment or creativity is needed. Code handles the repetitive work: timing, layout, loudness, validation and uploads.
2. **Every stage is a pure function of stored inputs.** `inputs (DB rows + files) → outputs (DB rows + files)`, with an input hash. Re-running a stage with the same hash returns the cached output instead of spending money again.
3. **Contracts over code generation.** The storyboard is JSON validated by a schema, and Remotion renders it through reusable components. We never generate new TSX per episode.
4. **Character identity is an asset, not a prompt.** The character is rendered from an approved rig/pose library. Generative image models never draw the hero.
5. **Fail closed on publishing.** Any missing proof (facts, rights, QA, metadata, approval) blocks upload.
6. **Simple infrastructure first.** Postgres + filesystem + one worker. Redis, Celery or S3 are added only when measurements justify them.

## 2. Component view

```
                         ┌─────────────────────────────────────────┐
                         │      AI CREATOR STUDIO (FastAPI+HTMX)   │
                         │ overview · calendar · agents · review   │
                         │ approvals · publishing · analytics      │
                         └───────────────┬─────────────────────────┘
                                         │ REST (internal)
┌──────────────┐   enqueue   ┌───────────▼───────────┐   reads/writes   ┌──────────────┐
│  Scheduler   ├────────────►│     Orchestrator      │◄────────────────►│  PostgreSQL  │
│ (APScheduler │             │ workflow state machine│                  │ state, jobs, │
│  Asia/Jakarta│             │ + job queue (SKIP     │                  │ costs, logs  │
└──────────────┘             │   LOCKED) + retries   │                  └──────────────┘
                             └───────────┬───────────┘
                                         │ dispatch stage
         ┌───────────────────────────────┼─────────────────────────────────┐
         ▼                               ▼                                 ▼
 ┌───────────────┐              ┌────────────────┐                ┌─────────────────┐
 │ Content agents│              │ Production     │                │ Distribution    │
 │ research      │              │ visual director│                │ thumbnail+SEO   │
 │ topic select  │              │ asset gen      │                │ publisher (YT)  │
 │ fact-check    │              │ voice          │                │ analytics       │
 │ script        │              │ animation/rend.│                └────────┬────────┘
 │ storyboard    │              │ QA             │                         │
 └──────┬────────┘              └──────┬─────────┘                         │
        │                              │                                   │
        ▼                              ▼                                   ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │ Provider layer (metered, cached, retried):  LLMProvider · ImageProvider ·        │
 │ TTSProvider · STT (local WhisperX) · MusicLibrary · YouTubeClient · Storage      │
 └──────────────────────────────────────────────────────────────────────────────────┘
        │                              │
        ▼                              ▼
 ┌──────────────┐              ┌──────────────────────────────┐
 │ External APIs│              │ Render engine                │
 │ Claude,Gemini│              │ Node render-server (Remotion)│
 │ OpenAI, 11L, │              │ + FFmpeg post (concat, R128, │
 │ YouTube      │              │   mux, captions, checks)     │
 └──────────────┘              └──────────────────────────────┘
```

## 3. Code layout (proposed)

```
ai-motion-graphic-kids-youtube/
├─ src/factory/
│  ├─ config/          settings (pydantic-settings), model tiers, budgets, brand
│  ├─ db/              SQLAlchemy models, Alembic migrations, repositories
│  ├─ orchestrator/    workflow definitions, state machine, job queue, scheduler
│  ├─ agents/          one module per agent: prompt templates + Pydantic I/O schemas
│  ├─ providers/       llm/, image/, tts/, stt/, music/, youtube/ (+ fakes for tests)
│  ├─ media/           ffmpeg wrappers, loudness, captions (SRT/VTT), viseme mapping
│  ├─ qa/              technical checks, content review, report builder
│  ├─ storage/         Storage interface; LocalStorage; S3Storage (later)
│  ├─ costs/           metering, pricing tables, budget guard
│  ├─ studio/          FastAPI app + templates (dashboard)
│  └─ cli.py           `factory run-episode`, `factory retry-stage`, …
├─ remotion/           Remotion project: components, Episode composition, render-server.mjs
├─ brand/              brand tokens JSON, character rig contract, style guides
├─ schemas/            JSON Schemas exported from Pydantic (storyboard, rig, …)
├─ content/            episode workspaces (gitignored), see §6
├─ tests/              unit, contract, integration, golden-episode
└─ docs/
```

## 4. Workflow engine
- **Workflow** = an ordered DAG of **stages** (see WORKFLOW_SPECIFICATION.md). An `episode` instance holds one `production_job` per stage.
- **Job queue** = the `production_jobs` table. Workers claim jobs with `SELECT … FOR UPDATE SKIP LOCKED`. Lanes:
  - `llm`: concurrency 4;
  - `media`: concurrency 2;
  - `render`: concurrency 1 per host;
  - `publish`: concurrency 1.
- **Status machine per job:**
  `pending → queued → running → succeeded | failed_retryable → (retry with backoff) | failed_permanent | awaiting_approval | cancelled | skipped`
- **Idempotency:** `input_hash = sha256(stage_version + canonical inputs)`. If a succeeded job with the same hash exists, its outputs are reused.
- **Human-in-the-loop:** gate stages put the episode into `awaiting_approval`, and the dashboard's approve or reject (with notes) resumes it. A rejection creates a new revision of the upstream stage with the notes attached.
- **Cancellation:** sets a flag on the episode. Workers check it between stages and between long sub-steps (e.g. per scene render).

## 5. Provider layer
Every external call goes through `Metered[Provider]`, which:
1. checks the budget guard (hard limit → raise `BudgetExceeded`, job paused);
2. looks up the response cache by request hash (deterministic stages);
3. calls the provider with timeout and retry. Retryable conditions are 429, 5xx and network errors, with exponential backoff and jitter. 4xx is not retried;
4. validates the response against a Pydantic schema;
5. writes `model_usage` (provider, model, units, cost, latency, job id).

Secrets come from env only. Logs pass through a redaction filter (tokens, keys, OAuth codes).

## 6. Asset storage layout
```
content/<yyyy>/<mm>/ep-<nnn>-<slug>/
  research/      brief.json, sources/*.txt (fetched snapshots), factcheck.json
  script/        script.v<k>.json, script.v<k>.md
  storyboard/    storyboard.v<k>.json, preview.html, stills/*.png
  assets/images/{backgrounds,props,diagrams}/  (episode-specific; shared library lives in library/)
  assets/characters/                            (rendered pose frames if per-episode)
  audio/{vo,music,sfx,mix}/
  subtitles/     en.srt, en.vtt
  renders/       scenes/<scene_id>.<hash>.mov|mp4, episode.v<k>.mp4, shorts/
  thumbnails/    candidates/*.png, final.png
  metadata/      youtube.json
  qa/            qa-report.json, qa-report.md, frames/
  logs/
library/  (cross-episode reusable assets: environments, props, music beds, sfx, character pose packs)
```
The DB stores relative storage keys plus sha256, size and mime. Files are never stored in Postgres.

## 7. Rendering architecture
1. The storyboard JSON is validated and resolved into a **render plan**: per-scene props, including resolved asset URLs, VO timing, visemes, captions and SFX cues.
2. The Node `render-server.mjs` is long-lived: it bundles once and keeps one browser, receiving JSON-lines requests. The pattern is ported from the existing ai-video-editor-remotion repo.
3. **Scene-level render** to an intermediate (`scene_id + props_hash + code_hash` → cache key). Only changed scenes are re-rendered.
4. FFmpeg concat of the scenes, then the audio mix: VO + music with sidechain ducking + SFX, loudness-normalised to −14 LUFS / −1 dBTP. Mux to H.264 High, yuv420p, AAC 48k, `+faststart`.
5. Previews: a low-res (540p) full render and per-scene stills for storyboard approval.

## 8. Quality and safety gates (fail-closed)
| Gate | After stage | Blocks on |
|---|---|---|
| G1 Topic safety | Topic selection | Unsafe/frightening/duplicate topic |
| G2 Fact gate | Fact-check | Any claim `unsupported`/`contradicted`; <2 sources on a key claim |
| G3 Script approval | Script validation | Human (APPROVAL_REQUIRED) or automated rubric (FULL_AUTOMATION) |
| G4 Rights gate | Asset/voice/music | Any asset without provenance + licence ref |
| G5 Technical QA | Render | Black frames, silence, clipping, wrong res/fps, duration out of range, A/V drift |
| G6 Content QA | Render | Character off-model, unreadable text, script/audio mismatch (WER), safety |
| G7 Metadata gate | SEO | Missing title/description/MFK flag/category/thumbnail; misleading-claim check |
| G8 Publish approval | Pre-upload | Mode-dependent (see API_INTEGRATION_PLAN.md) |

## 9. Non-functional targets (initial)
- Episode wall-clock time (excluding human waits): under 2 h.
- Any single failed stage is retryable without redoing successful upstream stages.
- Cost per episode is recorded to ±5% of the provider invoice.
- Zero secrets in logs or DB (only encrypted OAuth tokens).
- Nightly Postgres dump plus `content/` rsync to backup storage; restore drill monthly.
