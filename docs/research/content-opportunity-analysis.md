# Content Opportunity Analysis

Status: Phase 0 · hypotheses to validate with search-demand tools and our own analytics. Tag: [A] unless stated.

## 1. Scoring model (used by the Topic Selection Agent)
Each candidate is scored 1–5 on the brief's dimensions, then combined with a weighted sum (weights are configurable and tuned later from analytics):

| Dimension | Weight | Signal sources |
|---|---|---|
| Curiosity potential | 0.20 | "Why/how/what if" phrasing, surprise factor of the twist fact |
| Educational value | 0.20 | Curriculum alignment (NGSS / UK KS2 science), transferable concept |
| Storytelling potential | 0.15 | Can the character physically *go* somewhere? Is there a natural mystery? |
| Visual potential | 0.15 | Cutaways, scale, motion, transformation |
| Source reliability | 0.15 | Number of tier-1 sources found (gate: <2 means ineligible) |
| Topic freshness | 0.10 | Not covered by us in the last N episodes; low semantic similarity to our catalogue |
| Production feasibility | 0.05 | Reuse of existing environments/props; complexity estimate |

Hard gates (fail = ineligible):
- safety review (frightening, dangerous-to-imitate, medical advice);
- <2 reliable sources;
- duplicate of a scheduled or published episode;
- requires a copyrighted character or brand.

## 2. Launch slate (first 12 episodes): priority pillars only

| # | Pillar | Central question | Adventure hook | Twist (verify!) |
|---|---|---|---|---|
| 1 | Science & Space | Why is the sky blue? | Compass shrinks the hero to photon size | Sunsets are red for the same reason |
| 2 | Nature | How do octopuses change colour? | Coral-reef dive | Several octopus species are thought to be colour-blind, yet still camouflage |
| 3 | How Things Work | How does a giant plane stay in the air? | Ride on a wing | Wings also push air *down* (Newton's third law) |
| 4 | Nature | Why do cats purr? | Tiny-sized tour of a cat's throat | Purring may happen while healing or stressed, not just when happy |
| 5 | Science & Space | What's inside the Sun? | Layer-by-layer descent | Light from the core takes a very long time to escape (verify range) |
| 6 | How Things Work | How does your heart pump without stopping? | Ride through a heart | Its own electrical "pacemaker" |
| 7 | Nature | How do bees make honey? | Hive heist (friendly) | Number of flowers per spoonful (verify) |
| 8 | Science & Space | Why does the Moon change shape? | Orbit-eye view | We always see the same face |
| 9 | How Things Work | How does a toilet flush? | Pipe-slide adventure | Siphon physics |
| 10 | Nature | Why are flamingos pink? | Lake expedition | Diet pigments |
| 11 | Science & Space | What makes a volcano erupt? | Magma chamber | Volcanoes on other worlds |
| 12 | How Things Work | How do touchscreens know where you tap? | Inside the glass | Gloves don't work: conductivity |

All twists are *candidates*. The Fact-Checking Agent must verify each one, or it gets replaced. Episodes 1–3 double as the **pilot set** for Milestone 1/2 quality calibration.

## 3. Series formats (repeatable without becoming "inauthentic content")
Variation is built into the template, so videos are not mass-produced clones:
- **Main Quest** (5–8 min): the standard Question→Adventure→Discovery episode.
- **Compass Glitch** (5–6 min): the compass malfunctions, which drives comedic "what if" scenarios (pillar 5, later).
- **Time Jump** (6–8 min): history pillar (introduced after month 2).
- **Shorts**: the Twist fact as a 30–50 s standalone, derived from episode scenes.

Each episode must have unique narrative beats, locations and analogies. QA includes a *similarity check* against the catalogue: script embedding cosine plus structure-repetition heuristics, to stay clear of YouTube's "inauthentic/repetitive" guideline.

## 4. Seasonal and curriculum calendar (northern-hemisphere school year; tune with analytics)
- Sep–Oct: back-to-school topics (human body, plants).
- Oct: space (World Space Week, 4–10 Oct).
- Dec: winter science (snowflakes, why it's cold).
- Mar–Apr: Earth Day (22 Apr) nature topics.
- Jun–Aug: summer curiosity (oceans, insects, weather).

## 5. Feedback loop design
Analytics → Research Agent signals (weekly):
- retention curve per scene (map `elapsedVideoTimeRatio` to scene IDs to find the scenes where kids drop off);
- CTR per thumbnail style;
- average view duration per pillar/format;
- search-traffic terms (Analytics API `insightTrafficSourceDetail`, if available for MFK).

**Guardrail:** the optimisation target is a composite: retention + educational QA score + views. It is never views alone (brief §8, Agent 13).
