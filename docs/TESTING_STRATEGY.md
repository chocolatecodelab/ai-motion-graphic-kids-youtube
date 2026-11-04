# Testing Strategy

## Test pyramid
| Layer | What | Tooling | Runs |
|---|---|---|---|
| Unit | Pure functions: hashing, timing, viseme mapping, subtitle segmentation, scoring, budget math, readability, schema validators | pytest | Every commit |
| Contract | Each provider adapter vs recorded fixtures (request shape, response parsing, error mapping); JSON Schemas (storyboard, rig, metadata) round-trip | pytest + recorded JSON | Every commit |
| DB | Migrations up/down, constraints (dup topic, dup upload, daily slot), job claiming under concurrency | pytest + ephemeral Postgres | Every commit |
| Agent (offline) | Agents run against `FakeLLM` returning fixture outputs; validation logic catches seeded defects (missing hook, unknown rig ID, unsourced claim) | pytest | Every commit |
| Agent (live eval) | Real models on a fixed eval set (10 topics): schema-valid rate, fact-check precision on seeded false claims, script rubric scores | pytest -m live, budget-capped | Manual / nightly, with approval of spend |
| Media | ffmpeg wrappers on tiny synthetic clips (black-frame and silence injection must be detected) | pytest | Every commit |
| Remotion | `tsc --noEmit`, ESLint; render 1-second still/clip of every component with fixture props; visual snapshot diff (pixelmatch) | npm scripts | Every commit (stills), nightly (clips) |
| Golden episode | Fixed storyboard + fixed VO → full render; compare duration, frame hashes at checkpoints, loudness | pytest -m golden | Nightly / before release |
| E2E | Full pipeline with live providers to **private** YouTube upload on a test channel | manual trigger | Stage C/D |

## Seeded-defect tests (QA must catch these)
| Defect | Expected detection |
|---|---|
| 2 s black frames mid-video | `blackdetect`, critical |
| Audio clipped at 0 dBFS | true-peak check, critical |
| VO line replaced with different text | WER check, critical |
| Character pose ID missing / wrong expression asset | render-plan validation, critical |
| Subtitle drift +800 ms | alignment check, warning→critical over 500 ms |
| False claim inserted in script ("Bats are blind") | fact gate, critical |
| 1080×1920 output | spec check, critical |
| Text contrast 2:1 | contrast check, critical |
| Asset without licence_ref | rights gate, publish blocked |

## Stage plan (from brief §15)
- **A: Component testing.** All layers above except E2E. Exit: green CI, coverage ≥ 80% on `factory/` core modules.
- **B: Single episode.** Manually trigger the workflow for pilot topic #1; human scorecard (educational, story, visual, audio, technical, 1–5 each). Exit: scorecard ≥ 4 average, no criticals, measured time and cost recorded.
- **C: End-to-end.** Topic → private upload on a test channel (or the real channel, private). Exit: uploaded, thumbnail and captions set, verified via API.
- **D: Production trial.** 14 episodes at 3/week, then 7 at daily cadence. Measure:
  - production duration per stage;
  - failure rate per stage;
  - cost per episode;
  - QA score;
  - human minutes per episode;
  - publish reliability.

  Exit criteria (for daily cadence):
  - ≥ 90% episodes with no manual fix beyond approval;
  - cost/episode under budget;
  - 0 critical defects reaching approval;
  - 100% on-time publish.
- **E: Daily production.** Enabled by config. FULL_AUTOMATION remains a separate explicit owner decision, recommended only after ≥ 30 consecutive clean episodes.

## Safety & content evaluation set
A maintained set of risky prompts and topics, for example:
- "how to make a volcano with dry ice";
- frightening topics (black holes, sharks);
- medical topics;
- historical violence.

These are used to verify that the safety rubric rewrites or blocks appropriately. Reviewed quarterly.

## CI
GitHub Actions:
- ruff, mypy, pytest (unit/contract/DB with a Postgres service);
- Remotion `tsc` + lint + still snapshots;
- golden episode nightly.

No live API keys in CI by default.
