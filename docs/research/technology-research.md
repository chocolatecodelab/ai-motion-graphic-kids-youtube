# Technology Research & Comparison

Status: Phase 0 draft · 2026-11-04. Prices are USD list prices found via search summaries of vendor pages and should be **re-verified on the vendor page before purchase**. In this environment, direct fetches to vendor and Google domains were blocked by network policy.

Selection criteria: quality · reliability · API availability · cost/video · rate limits · licensing and commercial rights · automation · maintenance.

## 1. LLMs and agents

| Provider / model | Price (in/out per 1M tok) | Use in factory |
|---|---|---|
| Anthropic **Claude Opus 5.5** (`claude-opus-5-5`) | $4 / $20; cache read $0.20 | Scriptwriting, fact-check adjudication, QA judgement (highest-stakes reasoning) |
| Anthropic **Claude Sonnet 5.5** (`claude-sonnet-5-5`) | $2 / $10; cache read $0.20 | Research synthesis, storyboard JSON, visual direction, SEO |
| Anthropic **Claude Haiku 5.5** (`claude-haiku-5-5`) | $0.10 / $0.50 (≤100K prompt) | Classification, dedupe, claim extraction, cheap validators |
| Message Batches API | 50% off, async | Nightly research and topic scoring (not latency-sensitive) |
| Claude server tools `web_search` / `web_fetch` | per-search fee plus tokens (verify current rate) | Research Agent with domain allowlists; fetch gives quotable source text |
| Google Gemini / OpenAI GPT | — | Secondary providers behind the same interface (fallback, A/B tests, vision QA cross-check) |

Source: Anthropic model and pricing table (claude-api reference, cached 2026-10-06).

**Decision:**
- Claude is the primary provider, behind a `LLMProvider` interface (`generate_structured(schema, messages, tier)`).
- Agents call *tiers* (`reasoning` / `standard` / `fast`), not model IDs. Model IDs live in config.
- Use structured outputs (JSON schema), so every agent output is validated with Pydantic.
- Key API notes (current API):
  - adaptive thinking plus `output_config.effort` (Opus 5.5 defaults to `medium`; set it explicitly);
  - prefill and forced `tool_choice` are not available on 5.5 models;
  - handle `stop_reason == "refusal"`.

**Not using an agent framework (LangGraph, CrewAI etc.) initially.** Each "agent" is a deterministic stage that makes one or a few structured LLM calls. Our orchestrator owns state, retries and costs. This is simpler to test, cheaper, and matches the brief: "do not create agents merely to increase their number".

## 2. Web research and fact-checking
- **Primary:** Claude `web_search` with an `allowed_domains` allowlist (NASA, NOAA, NIH/MedlinePlus, Smithsonian, Natural History Museum, Britannica, National Geographic, USGS, ESA, university `.edu`/`.ac.uk`, Royal Society, museums) plus `web_fetch` with citations to capture exact supporting quotes.
- **Rule:** every claim in the final script maps to at least 2 independent sources, or at least 1 primary institution source, with a stored quote and URL. The fetched page snapshot (text) is stored in `research_sources` for audit.
- **Optional later:** Wikipedia as a *discovery* source only, never as sole evidence.

## 3. Image generation (backgrounds, props, concept art, thumbnails)

| Model | ~Price/image | Notes |
|---|---|---|
| Gemini 2.5 Flash Image ("Nano Banana") | $0.039 (1K); batch $0.0195 | Cheap; multi-image reference input for style consistency [S: benchlm, myarchitectai] |
| Gemini 3.1 Flash Image ("Nano Banana 2") | $0.067 (1K) – $0.151 (4K) | Newer and stronger [S] |
| Gemini 3 Pro Image ("Nano Banana Pro") | $0.134 (1–2K), $0.24 (4K) | Highest-quality Google option [S] |
| OpenAI GPT Image 2 / 2.5 | ~$0.005–0.21 depending on size and quality; GPT Image 1.5 high 1536×1024 = $0.20 (OpenAI model page, deprecated) | Strong instruction following and text rendering; 1.5 and 1-mini retire 2026-12-01 [S: costgoat] |

**Decision:**
- Use Gemini Flash Image as the default for environment plates and props (cost), with a pinned style-reference set.
- Use GPT Image / Nano Banana Pro for thumbnails and hero frames.
- Everything sits behind an `ImageProvider` interface.
- Every asset is stored with prompt, model, seed/params, reference IDs, licence terms version and cost, which gives provenance for the "unverified asset rights" publish block.
- **Never use image generation for the main character's per-shot rendering** (see §4).

## 4. Character consistency: the critical design decision

Generative models still drift on identity across hundreds of shots, and the 2026 AI-kids-content terminations were specifically about warped characters. Options:

| Option | Consistency | Look | Automation | Cost/ep | Effort |
|---|---|---|---|---|---|
| A. Per-shot AI image or video of the character (reference-conditioned) | ❌ drifts | varies | high | $$–$$$ | low |
| B. **2.5D cut-out puppet**: layered vector parts (head, eyes, brows, mouth visemes, arms) animated in Remotion | ✅ perfect | flat or soft-shaded 2D | high | ~$0 | medium |
| C. **3D-rendered pose library**: a rigged stylised 3D model; Blender headless renders a library of poses, expressions and visemes as PNG sequences; Remotion composites them | ✅ perfect | stylised 3D (matches brief) | high | ~$0 at runtime | high upfront (model and rig) |
| D. Live 3D in Remotion via `@remotion/three` (React Three Fiber) with GLB plus morph targets | ✅ perfect | stylised 3D | high | ~$0 | high; WebGL in headless Chrome needs the ANGLE renderer ([Remotion docs](https://remotion.dev/docs/three)) |

**Recommendation:**
- Build the system around a **Character Rig Contract**: a JSON listing available poses, expressions, visemes and actions. The animation engine only references rig IDs, so B, C and D are interchangeable implementations.
- **MVP: B.** Fastest to a working episode; deterministic.
- **Production target: C (or D).** Commission or produce a stylised 3D model once the Character Bible is approved.

Lip-sync: viseme timeline derived from TTS character timestamps (ElevenLabs "with timestamps") or forced alignment (WhisperX, already in the existing repo), mapped to about 8–10 mouth shapes. Rive is also viable (`@remotion/rive` exists), but it adds a proprietary editor dependency.

## 5. Text-to-speech

| Provider | Price | Notes |
|---|---|---|
| ElevenLabs Multilingual v2 / v3 | ~$0.10 per 1K chars (~$0.12/min); Flash ~$0.05/1K [S: ElevenAPI pricing snapshot Jul 2026] | Most expressive; voice design (synthetic, not a cloned real person); timestamps endpoint; commercial use on paid plans only |
| Google Cloud TTS Chirp 3 HD | ~$30 per 1M chars (~$0.03/min), 1M free/month [S] | Cheap and reliable fallback; less character acting |
| OpenAI gpt-4o-mini-tts | token-priced ($0.60 in / ~$12 out per 1M) [S, conflicting] | Steerable delivery via instructions |

**Decision:**
- ElevenLabs is primary, with a *designed* voice per character (no real-person clone, so likeness rights stay clean). Chirp 3 HD or OpenAI is the fallback behind `TTSProvider`.
- Voice settings are versioned per `character_version`.
- Recording the licence and plan tier at generation time is mandatory.

## 6. Speech-to-text (QA, not production)
- WhisperX / faster-whisper running **locally**. The existing repo already has `transkrip.py` with word-level alignment.
- Used for subtitle-accuracy QA (WER of rendered audio vs script) and forced alignment when the TTS provider lacks timestamps. Cost $0 (CPU).

## 7. Music and SFX

| Option | Licence clarity | Cost |
|---|---|---|
| **Procedural SFX and music synthesised in code** (existing `sfx.py`, `musik.py`) | ✅ we own it outright | $0 |
| Curated licensed library (e.g. a subscription library, or YouTube Audio Library tracks downloaded manually) | ✅ if licence terms are stored per track | $0–$30/mo |
| ElevenLabs Music | marketed as commercially cleared on paid plans [S]; verify terms | plan-based |
| Suno / Udio | ⚠️ litigation, unsettled licensing [S] | — |

**Decision:**
- Procedural SFX from day one.
- Music comes from a small curated library of licensed beds (5–10 brand themes), with a licence file per track, plus an optional ElevenLabs Music integration.
- No Suno/Udio.
- The publish gate blocks any audio asset without a `licence_ref`.

## 8. Animation and rendering
- **Remotion 4** (React → video), already used in the existing repo at v4.0.538.
  - Licence: free for individuals and companies with **≤3 employees**. Larger companies need a Company License (per-seat "Creators" plan, or "Automators" at ~$0.01/render with a $100/mo minimum) [S: remotion.dev/docs/license via search]. **Owner must confirm company size.**
- **FFmpeg 6.1** (installed). Used for concat, loudness normalisation (EBU R128, −14 LUFS integrated target for YouTube, −1 dBTP), muxing, black/freeze/silence detection and thumbnail extraction.
- Existing repo pattern worth reusing: a long-lived `render-server.mjs` (bundle once, one browser, JSON-lines protocol) plus content-hash render cache (`remotion_jembatan.py`).
- AI video generation (Veo/Kling/Runway): **not in the core path**. Possibly used later for short atmospheric B-roll inserts (no character), with its own QA and provenance.

## 9. YouTube publishing and analytics

| Item | Finding | Tag |
|---|---|---|
| Upload | `videos.insert`, resumable upload; `status.privacyStatus`, `status.publishAt` (scheduled, requires private), `status.selfDeclaredMadeForKids`, `status.containsSyntheticMedia` (A/S disclosure, added Oct 2024) | [E] YouTube Data API docs / revision history |
| **Audit lock** | **Videos uploaded via unverified API projects created after 2020-07-28 are restricted to private** until the project passes a compliance audit | [E] videos.insert docs |
| Quota | Default 10,000 units/day. Sources conflict on `videos.insert` cost (100 vs 1,600 units); `thumbnails.set` = 50. Either way, 1 upload/day fits. | [E]/[S] |
| OAuth | In "Testing" status, refresh tokens expire every 7 days, so unattended operation needs "In production" status (sensitive scopes → Google verification) | [S] Google forum, vendor blog |
| Analytics | YouTube Analytics API `reports.query`: views, watch time, average view duration, retention (`audienceWatchRatio` by `elapsedVideoTimeRatio`), subscribers gained. **Impressions and CTR** reportedly come only from the **Reporting API** bulk "reach" reports (up to 48h delay) | [S] (verify) |
| Custom thumbnails | Require a channel with intermediate/advanced features (phone verification) | [A] verify |

**Action items with lead time (start now, in parallel to M1):**
1. Create the Google Cloud project and apply for the YouTube API compliance audit.
2. Configure the OAuth consent screen and verification for `youtube.upload` and `yt-analytics.readonly`.
3. Verify the channel for custom thumbnails.

## 10. Orchestration and infrastructure

| Need | Choice | Why |
|---|---|---|
| Language | Python 3.12+ (orchestration); TypeScript (Remotion) | Matches the brief and the existing repo |
| DB | PostgreSQL 16 (installed) + SQLAlchemy 2 + Alembic | Relational state, JSONB for agent outputs |
| Queue | **Postgres-backed job table** (`SELECT … FOR UPDATE SKIP LOCKED`) + one worker process per lane | 1 video/day does not justify Redis+Celery; fewer moving parts. Redis/Celery stays a documented upgrade path |
| Scheduler | APScheduler inside the worker, or a systemd timer / cron | Timezone-aware (Asia/Jakarta default) |
| API + dashboard | FastAPI + server-rendered HTMX/Jinja (v1) | One language; real data only; can be swapped for Next.js later |
| Storage | Local filesystem behind a `Storage` interface (S3-compatible later) | Brief requirement |
| Secrets | `.env` (python-dotenv / pydantic-settings), never in DB or logs; OAuth tokens encrypted at rest (Fernet key from env) | Brief requirement |
| Observability | Structured JSON logs (structlog), `agent_executions` + `model_usage` tables, alert hook (email/Telegram) | Brief requirement |

## 11. Environment constraint discovered
This Claude Code cloud session's network policy blocks vendor domains (googleapis, openai, elevenlabs, remotion.dev were all refused). Consequences:
- **production must run on a host with open egress** (VPS or the owner's machine);
- development here can use mocks and recorded fixtures, unless the environment's network allowlist is extended.
