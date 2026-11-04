# Production Cost Analysis

Status: Phase 0 estimate · 2026-11-04. All figures are **planning estimates**, to be replaced by measured `model_usage` data after Milestone 1. Prices come from technology-research.md and must be re-verified on vendor pages.

## Reference episode (assumptions)
- 6 min long-form, 1920×1080, 30 fps = 10,800 frames.
- About 850–950 spoken words, about 5,500 characters of dialogue/narration.
- About 35 scenes. About 25 *new* generated images (backgrounds, props, diagrams), with the rest reused from the library. Two retries per image on average during the early months.
- 3 thumbnail candidates.
- One script revision loop and one storyboard revision loop.

## Variable cost per episode

| Stage | Driver | Low | High | Notes |
|---|---|---|---|---|
| Research + topic selection | Sonnet 5.5, ~250K in / 25K out, ~20 web searches; Batch API where possible | $0.40 | $1.20 | Batch halves the token part |
| Fact-checking | Haiku claim extraction + Opus 5.5 adjudication, ~200K in / 20K out | $0.50 | $1.30 | Source text is the main input |
| Script (+1 revision) | Opus 5.5, ~80K in / 25K out | $0.60 | $1.10 | Character Bible + brand guide cached (cache reads $0.20/M) |
| Storyboard + visual direction | Sonnet 5.5, ~100K in / 40K out | $0.40 | $0.80 | Large JSON output |
| Images | 25–75 generations × $0.039–0.17 | $1.00 | $12.00 | Biggest swing; falls as the asset library grows |
| Thumbnails | 3–6 × $0.13–0.21 | $0.40 | $1.30 | Premium model |
| Voice (TTS) | ~5.5K chars × 1.5 retakes × $0.10/1K | $0.80 | $2.00 | ElevenLabs API rate; a subscription may be cheaper |
| Music / SFX | procedural + licensed library | $0.00 | $0.00 | Library subscription counted in fixed costs |
| Render | Local CPU | $0.00 | $0.00 | Machine counted in fixed costs |
| QA | Vision review of ~60 sampled frames (Sonnet) + Opus content review + local WhisperX | $0.30 | $0.80 | |
| SEO metadata | Sonnet | $0.05 | $0.15 | |
| **Total variable** | | **≈ $4.50** | **≈ $20.50** | Target after optimisation: **< $8** |

Per-unit references:
- Generated image: $0.02 (Gemini Flash batch) – $0.21 (GPT Image high).
- Voice-over minute: ~$0.03 (Chirp 3 HD) – ~$0.12 (ElevenLabs v3/Multilingual).
- Render: $0 marginal on owned or rented CPU. Remotion Automators licence (if required) adds $0.01/render with a $100/mo minimum.

## Fixed monthly costs

| Item | Low | High | Notes |
|---|---|---|---|
| Production host (VPS 4–8 vCPU / 16 GB, or the owner's machine) | $0 | $80 | 8 vCPU recommended for daily renders |
| ElevenLabs plan (commercial rights) | $22 | $99 | Tier depends on characters/month (~250K chars/mo at 30 eps incl. retakes) |
| Music library subscription | $0 | $30 | Optional |
| Remotion Company License | $0 | $100+ | $0 if ≤3 employees |
| Backup storage (S3-compatible, ~200 GB) | $2 | $10 | |
| Domain/email/alerting | $0 | $10 | |
| **Total fixed** | **≈ $25** | **≈ $330** | |

## Monthly totals at 30 episodes
| Scenario | Variable | Fixed | Total |
|---|---|---|---|
| Lean (mature library, Gemini Flash, small team) | 30 × $5 = $150 | $40 | **≈ $190/mo** |
| Expected (first 3 months) | 30 × $10 = $300 | $150 | **≈ $450/mo** |
| Heavy (premium image models, many retries, Remotion licence) | 30 × $20 = $600 | $330 | **≈ $930/mo** |

Human time is not included. In APPROVAL_REQUIRED mode, owner review is estimated at 20–40 min/episode (script + final video), which is the real bottleneck at daily cadence.

## Storage
| Artifact | Size/episode |
|---|---|
| Final MP4 (H.264, 1080p, ~8 Mbps) | ~350 MB |
| Scene renders / intermediates (ProRes 4444 overlays are heavy) | 2–6 GB |
| Images, audio, JSON | ~200 MB |

Policy:
- keep finals, sources, JSON and audio forever;
- purge intermediates 14 days after publish;
- at 30 eps/mo, that is ~15 GB/mo retained plus a ~100 GB rolling working set.

## Render time (estimate, verify in M1)
Remotion at 1080p renders roughly 5–20 frames/s on 4–8 cores, depending on scene complexity, so a 6-min episode takes **≈10–35 min**. Scene-level caching means a revision re-renders only the changed scenes. This is acceptable for daily production on one host.

## Expected bottlenecks
1. **Human approval time.** Daily reviews by the owner. Mitigation: a good dashboard, diff-based re-review, and stage approval only at script + final.
2. **Image retries during style lock-in.** Mitigation: an asset library and reuse-first lookup by tags/embeddings.
3. **TTS retakes for mispronunciation.** Mitigation: a pronunciation lexicon (SSML/alias), plus the QA WER check pinpointing the bad line, so only that line is regenerated.
4. **YouTube quota/audit** (not cost, but a hard blocker). See API_INTEGRATION_PLAN.md.

## Budget controls (implemented in M1)
- `BUDGET_DAILY_USD`, `BUDGET_MONTHLY_USD`, `BUDGET_EPISODE_USD`, each with soft (warn) and hard (pause queue) thresholds.
- Every provider call goes through a metering wrapper that records tokens/units and cost *before* returning.
- Stage outputs are cached by input hash: a retry never repeats a successful expensive call.
