# AI Kids Educational Animation Factory

*Explore. Wonder. Discover.* An autonomous, observable production system for one original educational animation episode per day, for curious kids aged 8–12.

**Status:** Phase 0 (research & design) is complete. M1 is in progress. Done so far:
- foundations: config, DB schema + migrations, logging, `factory doctor`, tests;
- voice bake-off: hero (now Arka) = Kokoro `af_heart`, companion (now Lipa) = `af_sky`;
- job queue, worker and the `claude -p` LLM provider;
- the brief → script → script review (owner approval) → storyboard stages;
- voice (Kokoro per line, STT/WER check, line cache) and subtitles (SRT/VTT);
- storyboard v2 (shot types, angles, camera moves, character blocking + variety rules);
- Remotion renderer (`remotion/`, v4.0.538): vector character rigs,
  9 parallax background themes, motion-graphics components, transitions;
- timing (frame-accurate render plan, lip-flap curves) → render_scenes (cached scene clips) →
  assemble (episode MP4, -14 LUFS) → qa (technical QA report, blocks on critical defects).

**M2 in progress:**
- on-screen captions (current word highlighted, speaker colour) next to the SRT/VTT files;
- Character Bible v2 ([docs/creative/CHARACTER_BIBLE.md](docs/creative/CHARACTER_BIBLE.md)): **Arka & Lipa** replace Kai & Needle. The owner's React/SVG rig (`remotion/src/rig/`, rig.v2: Arka 14 poses × 10 expressions, Lipa 6 poses × 8 expressions) has been polished for smooth motion: soft joints, an eased walk, pose blending, prop fades, follow-through, and paper-wing flight;
- reference sheet [docs/creative/reference_sheet_v2.png](docs/creative/reference_sheet_v2.png) and motion check [docs/creative/rig_v2_motion_check.mp4](docs/creative/rig_v2_motion_check.mp4), approved by the owner (`character_version = 2`). Rebuild them in `remotion/` with `npx remotion still CharacterSheet` and `npx remotion render RigCheck`.

**M1 exit criteria met:** `uv run factory run-episode` takes the pilot brief to a QA-passed 1080p MP4. It stops once, for the owner's script approval; continue with `--episode <slug>`.

## Quickstart (Windows, owner machine)

Prerequisites: Python 3.12 + [uv](https://docs.astral.sh/uv/), Docker Desktop, Node 22+, FFmpeg, Claude Code CLI (`claude`).

```bash
copy .env.example .env
```

```bash
docker compose up -d postgres
```

```bash
uv sync --extra voice
```

```bash
uv run alembic upgrade head
```

```bash
uv run factory doctor
```

```bash
uv run pytest
```

### Run the pilot episode (script → review → your approval → storyboard)

```bash
uv run factory pilot
```

```bash
uv run factory worker --lane llm
```

```bash
uv run factory status ep-0001-why-is-the-sky-blue
```

Read the script and review under `content/<yyyy>/<mm>/ep-0001-why-is-the-sky-blue/` (`script/script.v1.md`, `script_validate/review.v1.md`), then approve and continue:

```bash
uv run factory approve ep-0001-why-is-the-sky-blue
```

```bash
uv run factory worker --lane llm
```

The storyboard stage also writes a visual review page, `storyboard/storyboard.vN.html`: a timeline, a layout sketch per scene, dialogue, graphics, sound effects and the claims with their sources. Rebuild it any time with `uv run factory storyboard-html <episode>`.

After approval, `uv run factory worker --all-lanes` runs both the storyboard (llm lane) and voice + subtitles (media lane: Kokoro TTS plus a Whisper check). The storyboard page then embeds a player for every voiced line and the full voice-over preview. Open it in a normal browser to play audio. `uv run factory sync <episode>` adds stages that were introduced after an episode was created.

Rendering needs `npm install` in `remotion/` once. The default `FACTORY_RENDER_QUALITY=preview` renders 960×540 clips for review, and they appear in the storyboard page (`uv run factory storyboard-html <episode>`). For the 1080p master, set `FACTORY_RENDER_QUALITY=final` and run `uv run factory retry <episode> render_scenes`; scenes are cached per quality. To preview a scene in Remotion Studio, run `npm run studio` inside `remotion/`.

`factory retry <episode> <stage>` re-runs one stage (upstream results are reused). `factory cancel <episode>` stops an episode.

Postgres listens on `127.0.0.1:25432`. The LLM runs through your Claude subscription (`claude -p`), so no API key is needed. See [docs/DECISIONS.md](docs/DECISIONS.md).

Start here: [docs/TECHNICAL_ASSESSMENT.md](docs/TECHNICAL_ASSESSMENT.md) · Owner decisions (override defaults): [docs/DECISIONS.md](docs/DECISIONS.md)

| Document | Purpose |
|---|---|
| [PROJECT_PLAN](docs/PROJECT_PLAN.md) | Milestones, parallel non-code track, risk register |
| [SYSTEM_ARCHITECTURE](docs/SYSTEM_ARCHITECTURE.md) | Components, workflow engine, storage, render, gates |
| [TECH_STACK_DECISION](docs/TECH_STACK_DECISION.md) | ADR table + reuse map from `ai-video-editor-remotion` |
| [DATABASE_SCHEMA](docs/DATABASE_SCHEMA.md) | Postgres entities, indexes, invariants |
| [AGENT_SPECIFICATIONS](docs/AGENT_SPECIFICATIONS.md) | 13 agents: inputs, outputs, validation |
| [WORKFLOW_SPECIFICATION](docs/WORKFLOW_SPECIFICATION.md) | Stage table, state machine, timeline, guards |
| [API_INTEGRATION_PLAN](docs/API_INTEGRATION_PLAN.md) | Claude, Gemini, OpenAI, ElevenLabs, YouTube APIs, publication modes |
| [TESTING_STRATEGY](docs/TESTING_STRATEGY.md) | Test pyramid, seeded defects, stages A–E |
| [DEPLOYMENT_GUIDE](docs/DEPLOYMENT_GUIDE.md) | Host, services, secrets, backups, monitoring |
| [COST_ESTIMATION](docs/COST_ESTIMATION.md) | Per-episode and monthly cost, budgets |
| [research/](docs/research/) | Market, competitors, technology, costs, content opportunities |
| [creative/CHARACTER_CONCEPTS](docs/creative/CHARACTER_CONCEPTS.md) | Three original hero concepts for selection |
