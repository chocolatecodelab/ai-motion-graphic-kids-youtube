# Decision Log

Decisions confirmed by the owner. These take precedence over the defaults proposed elsewhere in `docs/`. Where a design doc differs, this file wins until that doc is updated.

## 2026-11-04: Owner answers to Phase 0 questions

| # | Topic | Decision |
|---|---|---|
| D1 | Repository | `chocolatecodelab/ai-motion-graphic-kids-youtube` is the project home; pushing approved |
| D2 | AI providers | **Free-first stack** (below). Paid providers stay as optional adapters behind the same interfaces |
| D3 | Production host | **Owner's own computer** (OS/GPU to be confirmed) |
| D4 | Remotion licence | Single person (≤3 employees) → **free licence** applies; no Company License cost |
| D5 | Character | **Concept C "Kai & Needle"**; rig type **2D cut-out vector puppet** (MVP and production). The 3D pose library is deferred |

## D2: Free-first provider stack

| Function | Free choice | Licence / cost | Paid upgrade path (adapter, off by default) |
|---|---|---|---|
| LLM: script, fact-check, storyboard, QA review | **Claude through the owner's Claude subscription**, called headless with `claude -p` (Claude Code CLI) via a `ClaudeCodeCLIProvider` adapter, with JSON output validated by Pydantic | Included in the subscription, subject to plan usage limits. Anthropic changed how `claude -p` / Agent SDK usage is metered in mid-2026 (a separate monthly credit was announced, and its status was unclear in search results), so **verify current terms**. Plans are for individual use, which matches a one-person operation | Claude API key (pay-as-you-go), Gemini/OpenAI |
| Web research | Claude Code's built-in web search / fetch tools inside the same `claude -p` run, with a domain allowlist enforced in the prompt **and** re-checked in code (source URLs must match the allowlist, and quotes must be verbatim in the fetched snapshot) | Included | Claude API `web_search` |
| Text-to-speech | **Kokoro-82M** (local, runs on CPU) with stock voices: no cloning, so no likeness rights issue | Apache-2.0 (per model card; re-verify) | **Chatterbox** (MIT, emotion-exaggeration control, needs a GPU) if a GPU is available; ElevenLabs |
| Speech-to-text (QA, alignment) | faster-whisper / WhisperX local | MIT/BSD | — |
| Backgrounds, props, diagrams | **Vector illustration authored as SVG/React components** in brand style (written by Claude, reviewed, stored in a reusable library). Matches the 2D cut-out look and stays perfectly consistent | Owned outright | Local FLUX.1 [schnell] (Apache-2.0, verify; needs NVIDIA GPU about 12 GB+); Gemini/GPT Image |
| Thumbnails | Remotion still: rig pose + library scene + title text | Owned | Image model hero art |
| Music & SFX | Procedural synthesis (ported from `ai-video-editor-remotion`) | Owned | Licensed library / ElevenLabs Music |
| Animation & render | Remotion 4 + FFmpeg (local) | Free licence (D4) | — |
| YouTube Data / Analytics / Reporting APIs | Google Cloud project | Free within quota | — |

### Not used (licence or terms problems)
- Coqui XTTS-v2 weights: non-commercial licence.
- Gemini free tier for image generation: reports conflict on availability, and a forum post says billing has been required for images since Feb 2026.
- Suno/Udio: unsettled licensing.

### Consequences
- **Marginal cost per episode is about $0** (electricity plus the existing Claude subscription). Budgets now mainly track *subscription usage* (number of `claude -p` calls and tokens reported in the CLI JSON output) instead of dollars.
- **Throughput is bounded by subscription usage limits and local CPU.**
  - Mitigation: cache every stage by input hash (no repeated calls) and keep prompts compact.
  - Research runs as one larger call per day instead of many small ones.
- **Quality trade-offs to evaluate in M1:**
  - Kokoro is clear and natural but less "character acting" than ElevenLabs. A blind A/B test on the pilot decides whether a paid voice is worth it later.
  - Hand-authored SVG scenes take more Claude effort per new location, but the library grows, so later episodes mostly reuse scenes.
- `claude -p` runs on the owner's computer, which is also the production host (D3), so no API keys need to live in the project for the LLM.

## D3: Implications of running on the owner's computer
- Must be awake and online during the nightly pipeline window. Plan to run the schedule while the computer is usually on, or trigger runs manually.
- **Open question:** Windows, macOS or Linux? NVIDIA GPU (model/VRAM)? This determines:
  - Windows-native vs WSL2 setup;
  - Kokoro (CPU) vs Chatterbox (GPU);
  - whether local FLUX is an option.
- Backups: Postgres dump + `content/` sync to an external disk or cloud drive.

## 2026-11-04: Production host inspected (answers the D3 open question)

| Item | Found | Consequence |
|---|---|---|
| OS | Windows 11 Home (native; no WSL2 needed) | Python via `uv`, Postgres in Docker Desktop, scheduled runs via Windows Task Scheduler |
| CPU / RAM | AMD Ryzen 5 5500U (6C/12T), 15.4 GB | Remotion renders on CPU. M1 must measure real fps |
| GPU | Integrated AMD Radeon. **No NVIDIA/CUDA** | **Kokoro on CPU** is the voice. Chatterbox and local FLUX are **not viable** here (GPU-only, per D2) |
| Disk | ~717 GB free on D: | Enough for the content working set and backups |
| Tools present | Python 3.12, Node 24, FFmpeg 9.0.1, Docker 29.5, Claude Code CLI 2.1.x | `factory doctor` checks all of these |
| Ports | 5432/15432/55432 already used by other local apps | Project Postgres is mapped to **127.0.0.1:25432** |

## 2026-11-04: Character voices (owner pick from the Kokoro bake-off)

| Character | Kokoro voice | Speed | Bake-off speed on this CPU |
|---|---|---|---|
| **Kai** (hero) | `af_heart` | 1.0 | 1.26× real time (fastest of six candidates) |
| **Needle** (companion) | `af_sky` | 1.1 | 0.79× real time |

- Stock voices only (no cloning). Kokoro-82M weights are Apache-2.0.
- Word timestamps were returned for every line, so they can drive subtitles and lip-sync.
- The bake-off can be reproduced with `voice_bakeoff/run_bakeoff.py`.
- Set in config as `FACTORY_TTS_HERO_*` / `FACTORY_TTS_COMPANION_*`. Each `character_versions` row also stores `voice_id` + `voice_settings` so episodes stay pinned to the voice they were made with.

## 2026-11-04: Script review gate calibration (from the first live pilot runs)

| Finding | Severity | Effect |
|---|---|---|
| Safety or privacy issue | critical | **Stops immediately.** Never auto-revised; a human must decide |
| Other critical issue, or an unsupported *substantive* fact (mechanism, number, comparison) | critical / major | Blocks. The reviewer writes feedback to `inputs/feedback/script.vN.md` and the script is rewritten automatically, **max 2 rounds**, then it stops for a human |
| Any review score below 3/5 | — | Blocks (same revision loop) |
| Everyday knowledge or an exclamation that restates a verified claim | minor | **Warning only**, listed under "Check before approving" in the review report |
| Major clarity/story issues | major | Warning, listed for the owner |

The owner still approves every script in MANUAL and APPROVAL_REQUIRED mode. In the first pilot run the loop caught "blue waves are short **and quick**" (wrong: all colours travel at the same speed) and fixed it automatically.

## 2026-11-04: Storyboard direction (owner feedback on the pilot storyboard)

The owner approved the pilot storyboard (v2) to continue, with two requirements for the next storyboard iteration:

1. **Video previews, not only text.** Storyboard review should show a short low-res **animatic clip per scene** (540p, placeholder rig + real graphics + voice), not just a text sketch.
   - Built as soon as the Remotion scene components exist (M1 render step): the storyboard review page embeds one preview clip per scene.
   - Scene clips are cached by scene hash, so re-reviewing after an edit only re-renders the changed scenes.
2. **Dynamic, adventure-style staging.** Kai and Needle must not stay parked on the left and right. Storyboard schema v2 will add:
   - **shot type:** extreme wide, wide, medium, close-up, extreme close-up, over-the-shoulder, POV, insert;
   - **camera angle:** eye level, low, high, bird's-eye, tilted;
   - **camera moves:** zoom in/out, dolly, truck, pan/tilt, follow/track, whip pan, crane, rack focus, shake (for impacts), with keyframes over the scene;
   - **character blocking:** free x/y position, scale and depth (foreground/midground/background), facing direction, entrances and exits, and movement paths during the scene (walk, run, fly, float, shrink or grow), timed to lines;
   - **a variety rule** checked in code: no more than two consecutive scenes with the same shot type and blocking, and every adventure scene must include movement.

## 2026-11-05: M2 owner decisions

| # | Topic | Decision |
|---|---|---|
| D7 | Subtitles | **Both.** SRT/VTT files for YouTube CC, plus kid-friendly **on-screen captions** burned into the video: big rounded font, the current word highlighted, a speaker colour cue, kept clear of faces. The on-screen text always matches the script word for word |
| D8 | Final character design | **Designed in SVG by Claude** (no image API, free-first D2): Character Bible v1, turnaround/pose/expression reference sheet rendered from the real rig. **Owner reviews the sheet before `character_version = 1` is locked** |

## 2026-11-05: Characters replaced: Arka & Lipa (supersedes Kai & Needle)

The owner supplied a new character design and its React/SVG rig (`arka-lipa-character-bible.svg`, `arka-lipa-remotion.zip`). The owner asked for the characters only: voices and everything else stay as they are.

| Topic | Decision |
|---|---|
| Hero | **Arka** (speaker id `arka`), a young explorer: safari hat with a compass pin, teal kawung scarf, backpack with bedroll |
| Companion | **Lipa** (speaker id `lipa`), an origami bird folded from an old expedition map that glows when it finds a trail |
| Voices | Unchanged: Arka = Kokoro `af_heart` 1.0, Lipa = `af_sky` 1.1 (the former Kai/Needle voices) |
| Rig | The owner's rig is ported into `remotion/src/rig/` and polished by Claude (Character Bible v2, "Motion"): soft elbows and knees, a smooth eased walk cycle, a tidier crouch, prop grow/shrink during blends, head follow-through, jump anticipation, idle weight shift, and Lipa's asymmetric wingbeat with flexing wing tips |
| Contract | Rig catalogue `rig.v2` (`config/catalogue/rig_v2.yaml`). Old artifacts that use `kai`/`needle` and old pose/expression IDs still load and render through aliases |
| Review | Reference sheet `docs/creative/reference_sheet_v2.png` and motion check `docs/creative/rig_v2_motion_check.mp4`. **Approved by the owner on 2026-11-05: `character_version = 2` is locked** |
| Pilot | The pilot's approved script and audio still say "Kai"/"Needle". Re-voicing it with the new names needs a new script approval |

## 2026-11-04: First full render of the pilot (measured on the owner's laptop)

| Step | Result |
|---|---|
| Storyboard v2 (dynamic shots) | 9 scenes, 33 shots; passed all variety rules on the first try |
| Timing | 164.0 s episode, 4,920 frames, lip-flap curves from the voice audio |
| Render 540p preview | ~11 s per scene (≈1.6× real time) |
| Render 1080p final | 269 s for 164 s of video (0.61× real time); scene clips cached per quality |
| Assemble | H.264 + AAC, −14.5 LUFS integrated, −1.0 dBTP true peak |
| Claude usage for the whole pilot | 16 `claude -p` calls (≈$1.92 equivalent API cost, covered by the subscription) |

Technical QA (`qa` stage) on the 1080p final: **PASS, 95/100**.
- Clean: spec, decode, no black or frozen frames, −14.5 LUFS / −1.0 dBTP, no dropouts, speech WER 3.3%, subtitle text identical to the script, subtitle sync +147 ms, claims, rights.
- One warning: 3 silent gaps over 2.5 s, because there is no music bed yet.
- 12 seeded-defect tests prove QA catches black frames, wrong orientation, duration drift, clipping, dropouts, a replaced VO line, subtitle drift (+800 ms), mismatched subtitle text, unverified claims, fonts without a licence, and non-commercial voice licences.

Known limitations, to be addressed in M2 (art direction):
- Kai, Needle and the backgrounds are v0 placeholders drawn in code.
- Graphics shown in insert/graphic-focus shots can still overlap a character.
- Music and SFX are not mixed yet: voice only.

## 2026-11-04: Media tooling (owner: "use remotion, hyperframes, motion-skill, whisper, ffmpeg, threejs, yt-dlp where best practice says so")

| Tool | Decision | Reason |
|---|---|---|
| **Remotion 4** | ✅ Core renderer | Typed React components fit a reusable template library driven by storyboard JSON. Code from `ai-video-editor-remotion` can be ported. Free licence (D4) |
| **HyperFrames** (HeyGen, Apache-2.0, HTML→MP4) | ⏸ Evaluated, not adopted now. Kept as the documented fallback renderer | It does the same job as Remotion (headless Chrome + FFmpeg). Running two renderers doubles the template work. Its licence has no headcount threshold, so it is the exit route if the business grows beyond Remotion's free tier (>3 people). The storyboard JSON contract stays renderer-agnostic so a switch is possible |
| **Motion skills** (agent skills for motion design) | ✅ Dev-time only | The Remotion agent skills (`remotion-best-practices` etc.) guide Claude while writing components. They are not a runtime dependency. If "motion-skill" means a specific package, the owner should name it |
| **Whisper** (faster-whisper / WhisperX, local CPU) | ✅ QA + alignment | Transcript-vs-script WER check, subtitle timing fallback, lip-sync alignment. Already in D2 |
| **FFmpeg** | ✅ Core | Mixing, loudness (R128), concat, encode, blackdetect/silencedetect/freezedetect QA |
| **Three.js** via `@remotion/three` | ✅ Selective, inside Remotion only | For scenes that really need 3D: planets/orbits, the Sun's layers, molecules, exploded machines. Not for the characters (they stay 2D vector puppets, D5). Uses CPU software WebGL here, so render cost must be measured per component and cached per scene |
| **yt-dlp** | ❌ Not in the pipeline | YouTube's Terms of Service don't allow downloading videos without permission, and we must never reuse competitor footage. Competitor research uses the **YouTube Data API** for metadata (titles, durations, views, upload cadence, thumbnail URLs for side-by-side review only). Our own videos can be fetched through YouTube Studio / API if ever needed |
