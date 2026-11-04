# Tech Stack Decisions (ADR-style)

> Rows 4, 11, 12, 13, 15 and 22 are refined by owner decisions in [DECISIONS.md](DECISIONS.md): free-first providers, 2D vector puppet, own computer.

Each decision lists: context → decision → alternatives → revisit trigger.

| # | Area | Decision | Alternatives considered | Revisit when |
|---|---|---|---|---|
| 1 | Repo | New project in `chocolatecodelab/ai-motion-graphic-kids-youtube`. **Port** selected modules from `ai-video-editor-remotion` (same owner) rather than extending it | Extend the existing repo | — (domains differ: footage-based 9:16 shorts vs generated 16:9 long-form animation; existing repo is Windows/Indonesian-convention, approval-gated per human edit) |
| 2 | Orchestration language | Python 3.12+ | Node-only | — |
| 3 | Agent framework | **None**: plain stage functions + structured LLM calls | LangGraph, CrewAI, Claude Agent SDK, Managed Agents | A stage needs open-ended multi-step tool use (e.g. research gets complex). Then use the Claude tool runner *inside that stage only* |
| 4 | LLM | Claude (Opus 5.5 / Sonnet 5.5 / Haiku 5.5) via official `anthropic` SDK, behind `LLMProvider` tiers; Gemini/OpenAI adapters later | Single-vendor hardcode | Quality/cost data per stage from M1–M3 |
| 5 | Structured output | Pydantic v2 models → JSON Schema → `output_config.format` | Free text + regex | — |
| 6 | DB | PostgreSQL 16, SQLAlchemy 2 (typed ORM), Alembic | SQLite (too weak for concurrent workers), Mongo | — |
| 7 | Queue | Postgres job table with `SKIP LOCKED` | Redis+Celery/RQ/Dramatiq | >1 render host, or >10 episodes/day |
| 8 | Scheduler | APScheduler (in worker), TZ from config (`Asia/Jakarta`) | cron/systemd timer | Multi-host |
| 9 | Dashboard | FastAPI + Jinja + HTMX (+ Alpine for small widgets); Chart.js for analytics | Next.js SPA | Need for rich client interactivity or external users |
| 10 | Animation | Remotion 4.x (pin same minor as existing repo initially: 4.0.538) | Motion Canvas, After Effects + nexrender, Blender-only | — |
| 11 | Character rendering | **Rig Contract** abstraction; MVP = 2.5D layered-vector puppet in Remotion; target = 3D pose library (Blender headless pre-render) or `@remotion/three` | Per-shot AI image/video | See technology-research §4 |
| 12 | Image gen | Gemini Flash Image (default), GPT Image / Nano Banana Pro (thumbnails/hero) via `ImageProvider` | Midjourney (no stable official API historically), self-hosted SDXL/Flux (GPU ops burden) | Cost or style-consistency issues |
| 13 | TTS | ElevenLabs (designed voices) primary; Google Chirp 3 HD fallback | OpenAI TTS | Quality A/B in M1 |
| 14 | STT | faster-whisper / WhisperX local (QA + alignment) | Cloud STT | — |
| 15 | Music/SFX | Procedural SFX (ported `sfx.py`), curated licensed music beds with licence files | Suno/Udio (licensing risk) | — |
| 16 | Video post | FFmpeg 6.x via thin Python wrappers (ported from `sistem.py`) | MoviePy (slow, leaky) | — |
| 17 | Storage | Local FS behind `Storage` interface; S3-compatible (R2/B2/S3) later | Direct S3 from day one | Multi-host or disk > 70% |
| 18 | Secrets | `.env` + pydantic-settings; OAuth refresh token encrypted with Fernet (`TOKEN_ENCRYPTION_KEY`) | Vault | Team access grows |
| 19 | Logging | structlog JSON → file + DB `system_logs` (warn+); redaction processor | ELK | — |
| 20 | Packaging | `uv` for Python deps + lockfile; `npm ci` in `remotion/` | pip/poetry | — |
| 21 | Quality tooling | ruff, mypy (strict on `factory/`), pytest; ESLint + `tsc --noEmit` in Remotion | — | — |
| 22 | Runtime host | Linux VPS (8 vCPU/16 GB) or owner machine, systemd services; Docker Compose optional | Kubernetes | Multi-host |

## Deviations from the brief's recommended stack
- **Redis + Celery are not used initially.** The workload is about one episode per day with a handful of long stages. A Postgres-backed queue gives persistence, retries and observability with one less service. The interface (`JobQueue`) keeps a Celery swap cheap.
- **No multi-agent framework.** The brief asks for agents with clear responsibilities, and each one is implemented as a well-typed stage. This keeps cost and behaviour predictable.

## Reuse map from `ai-video-editor-remotion`
| Existing file | Reuse | Adaptation |
|---|---|---|
| `remotion/render-server.mjs` | ✅ port | Add codec presets for H.264 scene output; keep ProRes for alpha overlays only |
| `pipeline/scripts/remotion_jembatan.py` | ✅ port | Cache key = scene props + code hash; English naming |
| `pipeline/scripts/sistem.py` (ffprobe, loudness, hashing, JSON, colour contrast) | ✅ port subset | Strip Windows/temp-dir specifics |
| `pipeline/scripts/qa.py` (rule-ID registry, auto/manual checks, pass/fail report) | ✅ pattern | 16:9 rules, new content checks |
| `pipeline/scripts/sfx.py`, `musik.py`, `ducking.py` | ✅ port | Kid-friendly SFX palette; music used only as bed/stingers |
| `pipeline/scripts/transkrip.py` (WhisperX) | ✅ port | Used for QA + alignment |
| `pipeline/scripts/storyboard_html.py` | ✅ pattern | Storyboard approval page in the dashboard |
| `tokens/` design-token system | ✅ pattern | `brand/tokens.json` with the Explorer palette |
| `remotion/src/compositions/{Timeline,ChartGrow,Orbit,Penghitung,Partikel,Checklist,Penjelas}.tsx`, `lib/{Teks,font,motif,latar}` | ✅ adapt | Become infographic components (timeline, bar-grow, orbit diagram, counter, particles, checklist, explainer card) |
| `pipeline/fonts/` (Baloo 2, Lilita One, Luckiest Guy, Poppins + OFL licences) | ✅ copy with licences | Kid-friendly display fonts already licensed |
| ingest, roto, wajah (face), split, kamera, 9:16 safe zones | ❌ | Footage-specific |
