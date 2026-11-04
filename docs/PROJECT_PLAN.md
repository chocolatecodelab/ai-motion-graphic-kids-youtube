# Project Plan: Phased Roadmap

Each milestone ends with: tests green, a demo, measured results, updated docs, and the project left runnable. Durations are effort estimates for one developer working with Claude Code. They assume API keys are available when needed.

| Milestone | Goal | Key deliverables | Exit criteria | Est. |
|---|---|---|---|---|
| **M0 Research & design** (this) | Decide what to build | docs/research/*, 10 design docs, technical assessment, character concepts | Owner reviews; open decisions answered | done |
| **M1 Golden-episode vertical slice** | Prove the core loop renders a real, short episode end-to-end, and measure time and cost | Repo skeleton (uv, ruff, mypy, pytest, CI); config + `.env.example`; DB models + Alembic (core tables); Postgres job queue + state machine + retries + CLI; metered `LLMProvider` (Claude) + `TTSProvider` (ElevenLabs) with fakes; agents: script → script_validate → storyboard (topic and claims provided manually); storyboard JSON Schema v1; Remotion: Episode composition + 6 core components + **placeholder vector-puppet character** (rig contract v0, visemes, 6 expressions); render-server port; scene cache; FFmpeg assemble + loudness; technical QA (spec, black, silence, R128, WER) | A 2–3 min pilot ("Why is the sky blue?") rendered at 1080p from one `factory run-episode` command; any stage retryable independently; `model_usage` shows cost per stage; seeded-defect tests pass | 2–3 wks |
| **M2 Brand & character production** | Lock the visual identity | Character Bible v1 (selected concept), reference sheet, final rig (vector puppet v1 **or** 3D pose library per decision), brand tokens, Visual Style Guide, Motion Language guide, style-reference set; visual_plan + assets agents with asset library + provenance; procedural SFX + licensed music beds; parallax backgrounds | 3 pilot episodes at full length (5–8 min) pass human scorecard ≥ 4/5 | 3–4 wks |
| **M3 Research, fact-check, QA, packaging** | Automate the front and back ends | Research agent (allowlisted web search + snapshots); topic selection + dedupe; fact-check agent with verbatim-quote verification; full QA (vision on-model check, contrast, content review); thumbnail + SEO agent; MANUAL mode upload package | 5 episodes from topic to upload package with zero manual edits other than approvals | 2–3 wks |
| **M4 AI Creator Studio v1** | Human control surface | FastAPI + HTMX: overview, calendar, agent monitor, episode review (script, storyboard stills, assets, video player), QA report, approve/reject with notes, retry/cancel, settings (mode, budgets, schedule), cost views | Owner can run a full week of approvals from the dashboard only | 2 wks |
| **M5 YouTube integration** | Private upload + scheduling | OAuth flow + encrypted tokens; resumable upload; thumbnail; captions; publishAt; verification; APPROVAL_REQUIRED flow + notifications; duplicate-upload guards | Stage C E2E passes on the real channel (private); **audit status known** | 1–2 wks (+ Google audit lead time) |
| **M6 Analytics & feedback loop** | Learn from performance | Analytics + Reporting API ingestion; retention→scene mapping; insights feed into research/topic scoring; dashboard analytics module | Insights visibly change topic ranking; tests on fixture data | 1–2 wks |
| **M7 Production trial → daily** | Reliability at cadence | Trial (14 eps at 3/week, then 7 daily), monitoring/alerts, backups/restore drill, Shorts derivation (optional) | Stage D exit criteria (TESTING_STRATEGY.md) met → enable daily schedule | 4–5 wks calendar |
| Later | Scale & polish | FULL_AUTOMATION (owner-enabled after ≥ 30 clean eps), 4K, S3 storage, Celery if multi-host, additional pillars/formats | — | — |

> **Added 2026-11-04 (owner, see DECISIONS.md):** M1's Remotion step also delivers storyboard schema v2 (shot types, camera angles/moves, character blocking with movement paths, plus a variety check) and **per-scene animatic preview clips** embedded in the storyboard review page.

## Parallel non-code track (start immediately: long lead times)
1. Google Cloud project, YouTube Data API enabled, **apply for the API compliance audit**.
2. OAuth consent screen → production + verification for the YouTube scopes.
3. Channel set up: branding, MFK default audience = "Yes, it's made for kids", phone verification (custom thumbnails).
4. Accounts and keys: Anthropic, Google AI (Gemini), ElevenLabs (commercial plan), optionally OpenAI.
5. Name and trademark clearance for the channel name, character name and "Discovery Compass".
6. Remotion licence: confirm company headcount (≤ 3 → free).

## Risk register (top)
| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Character animation looks cheap or inconsistent | High | High | Rig contract; deterministic puppet/pose library; vision on-model QA; M2 dedicated to art direction; consider a freelance character artist for the final rig |
| R2 | YouTube API audit delayed or denied → uploads stuck private | Medium | High | Apply in week 1; APPROVAL_REQUIRED works pre-audit with manual publish in Studio |
| R3 | Platform policy: "inauthentic/mass-produced", AI-kids scrutiny, MFK quality principles | Medium | High | Unique narratives, similarity checks, visible sources, human approval, AI disclosure, quality over cadence |
| R4 | Factual errors reach kids | Medium | High | Fact gate with verbatim quotes, claim-ID tracing into the script, owner script approval, corrections workflow |
| R5 | Daily human review is unsustainable | High | Medium | Build a 2–3 episode buffer; streamline the dashboard; consider 3–5/week if quality slips |
| R6 | Licensing/provenance gap (images, voice, music) | Low | High | Provenance on every asset; rights gate; no Suno/Udio; designed voices |
| R7 | Low MFK revenue vs operating cost | High | Medium | Cost targets; diversification plan |
| R8 | Provider price/model churn (e.g. GPT Image 1.5 retiring Dec 2026) | High | Low | Provider abstraction; model IDs in config |
| R9 | Render time / host capacity | Low | Medium | Scene cache; 8 vCPU host; previews at 540p |
| R10 | Dev environment network blocks vendor APIs | Certain | Low | Fakes + fixtures; live tests on an open-egress host or an extended allowlist |
