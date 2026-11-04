# Technical Assessment (Phase 0)

Date: 2026-11-04 · Scope: brief §18 "Your first task", items 1–10.

## 1. Repository & infrastructure inspection
| Item | Finding |
|---|---|
| Target repo `chocolatecodelab/ai-motion-graphic-kids-youtube` | **Empty** (no commits). Greenfield. |
| Related repo `chocolatecodelab/ai-video-editor-remotion` | Mature Python + Remotion pipeline (~10.9K lines Python, 30+ TSX compositions, tests, QA engine) for **vertical 9:16 talking-head short videos** from real footage. Indonesian naming, Windows-first paths. Remotion 4.0.538, React 18. |
| Related repo `otcainovasi-sys/ai-office-3D-agent` | 3D "virtual office" dashboard for the Hermes agent. Not relevant beyond dashboard inspiration. |
| Dev container | Python 3.13, Node 22, FFmpeg 6.1, PostgreSQL 16 client/server, Redis 7, Docker, Chromium/Playwright, 4 vCPU, 15 GB RAM. |
| Credentials | **None present** for Anthropic API (production key), Gemini, OpenAI, ElevenLabs or YouTube. |
| Network | Dev session egress policy **blocks vendor APIs and docs** (googleapis, openai, elevenlabs, remotion.dev). Production must run on an open-egress host, or the environment allowlist must be extended. |

## 2. Market & competitors (summary)
Full reports: [market-research](research/market-research.md), [competitor-analysis](research/competitor-analysis.md), [content-opportunity-analysis](research/content-opportunity-analysis.md).
- Ages 8–12 heavily use YouTube (76% in 2019). The segment sits between the preschool-skewed character channels (Peekaboo Kidz ~7.7M subs) and the teen/adult animated explainers (TED-Ed ~23M, Kurzgesagt ~22–25M).
- Opening: an **adventure-format, character-led, source-transparent** series pitched exactly at 8–12.
- **Decisive constraints:**
  - Content for under-13s must be labelled Made for Kids. That label means contextual-only ads, and no comments, bell or end screens. The FTC fined Disney $10M in Nov 2025 for mislabelling.
  - YouTube's Jul 2025 "inauthentic content" policy targets mass-produced repetitive video.
  - In 2026, YouTube terminated AI kids channels after an NYT investigation, and 200+ experts asked Google to restrict AI video for kids.
  - Consequence: our system must win on **accuracy, consistency and originality**, not volume.

## 3. AI tools & APIs (summary)
Full report: [technology-research](research/technology-research.md).
| Function | Primary | Fallback |
|---|---|---|
| Reasoning/script/fact adjudication | Claude Opus 5.5 | — |
| Research, storyboard, SEO | Claude Sonnet 5.5 (+ web_search/web_fetch allowlisted) | Gemini / GPT |
| Cheap extraction/classification | Claude Haiku 5.5 | — |
| Backgrounds/props | Gemini Flash Image | GPT Image |
| Thumbnails/hero art | Nano Banana Pro / GPT Image | — |
| Hero character | **Rig (not generative)** | — |
| TTS | ElevenLabs designed voices | Google Chirp 3 HD |
| STT (QA/alignment) | WhisperX local | — |
| Music/SFX | Procedural + licensed beds | ElevenLabs Music |
| Animation/render | Remotion 4 + FFmpeg | — |
| Publishing/analytics | YouTube Data v3, Analytics, Reporting APIs | — |

## 4. Existing pipeline evaluation (`ai-video-editor-remotion`)
**Strengths:**
- clean "everything is data" philosophy (tokens + beat-sheet → render);
- content-hash render cache;
- an efficient long-lived Remotion render server;
- a rule-ID-based QA engine with pass/fail reports;
- procedural SFX/music (licence-clean);
- WhisperX alignment;
- a storyboard approval gate;
- unit tests.

**Gaps for this project:**
- built around *real footage* (ingest, rotoscope, face detection, 9:16 safe zones);
- no database, job queue, scheduler, LLM agents, TTS, character system, YouTube API or dashboard;
- Windows- and Indonesian-specific conventions.

**Verdict:** do not extend that repo. Port specific modules into the new project (see the reuse map in [TECH_STACK_DECISION.md](TECH_STACK_DECISION.md)).

## 5. Proposed architecture
See [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). In short:
- Python orchestrator with a Postgres-backed job queue and state machine;
- 13 typed agent stages with fail-closed gates G1–G8;
- metered provider layer with caching and budgets;
- Remotion scene-level rendering from schema-validated storyboard JSON, with the character rendered from a **Rig Contract**;
- FFmpeg post-production;
- FastAPI/HTMX "AI Creator Studio";
- YouTube publishing in three modes (APPROVAL_REQUIRED by default; FULL_AUTOMATION locked until explicitly enabled).

## 6. Highest-risk technical challenges (ranked)
1. **Character animation quality and consistency.** This is the hardest creative-technical problem. Generative per-shot images drift. Mitigation: a deterministic rig behind an abstract contract, plus vision QA.
2. **YouTube API audit and OAuth production status.** Without them, uploads are locked private and refresh tokens expire every 7 days. Lead time is outside our control.
3. **Platform-policy risk for AI kids content.** Requires originality checks, human approval, disclosure and sources.
4. **Factual accuracy at daily cadence.** Requires verbatim-quote verification, claim-ID tracing and an owner script gate.
5. **Human review throughput** at 7 episodes/week.
6. **Making 5–8 min engaging** with templated motion graphics without becoming repetitive (the component library breadth, plus the narrative variation built into the script agent).

## 7. Operating cost estimate
See [COST_ESTIMATION.md](COST_ESTIMATION.md):
- **$4.50–$20.50 variable per episode**;
- **≈ $190–$930/month at 30 episodes** (expected ≈ $450).

Human approval time (20–40 min/episode) is the real constraint.

## 8. Phased roadmap
See [PROJECT_PLAN.md](PROJECT_PLAN.md): M1 golden-episode slice → M2 brand and character → M3 research/fact/QA/packaging → M4 Studio → M5 YouTube → M6 analytics → M7 trial and daily.

## 9. Reusable components
- Render server and render cache;
- ffprobe/loudness/hash utilities;
- QA rule-engine pattern;
- procedural SFX and music, ducking;
- WhisperX alignment;
- storyboard HTML preview;
- design-token system;
- infographic-like Remotion compositions (Timeline, ChartGrow, Orbit, counter, particles, checklist, explainer card) and the text/font/motif libs;
- OFL-licensed kid-friendly fonts (Baloo 2, Lilita One, Luckiest Guy).

## 10. Built from scratch
- DB schema and migrations;
- job queue, state machine and scheduler;
- provider abstraction with metering, budgets and caching;
- all 13 agents and their prompts/schemas;
- storyboard JSON schema;
- the 16:9 Episode composition, scene components and transitions;
- the **character rig system and lip-sync**;
- asset library with provenance;
- TTS integration;
- the content QA (vision/on-model, WER, contrast) for animation;
- thumbnail/SEO;
- YouTube OAuth, upload and analytics;
- the AI Creator Studio dashboard;
- deployment, monitoring and backups.

## Recommended first milestone: **M1 "Golden-Episode Vertical Slice"**
Build the thinnest end-to-end path that produces a real 2–3 minute episode ("Why is the sky blue?") from a manually provided topic and claim set:

```
manual brief + claims → script (Opus) → script_validate → storyboard JSON (Sonnet)
→ TTS (ElevenLabs) + timestamps → visemes/subtitles → timing plan
→ Remotion scene renders (placeholder vector-puppet hero + 6 components) → FFmpeg mix/assemble
→ technical QA report
```
All of this runs on the real job queue, DB, cost metering and retry machinery.

Why this first:
- It de-risks the biggest unknowns (render quality, timing/lip-sync, real cost and time per minute of video) before investing in research automation or YouTube.
- Everything built is permanent infrastructure, not a throwaway prototype.

**Needs from the owner to start M1:**
- an Anthropic API key and an ElevenLabs key (commercial plan), or approval to use fakes and recorded fixtures until keys exist;
- a host with open egress for live runs.
