# Competitor Analysis

Status: Phase 0 draft · 2026-11-04. Tags as in market-research.md: [E] evidence, [S] secondary, [A] assumption.

Subscriber counts come from trackers (Social Blade, vidIQ) via search summaries. They are snapshots, not live figures.
**Rule: we analyse positioning and craft. We never copy scripts, characters, visual identities or titles.**

## 1. Landscape map

| Channel | Approx. subs | Age fit | Format | Positioning |
|---|---|---|---|---|
| TED-Ed | ~22.8M (Social Blade) [S] | 9+ / teens | 4–6 min animated lessons; a different animator per video | Prestige, "lessons worth sharing", school-aligned |
| Kurzgesagt | ~22–25M (sources conflict) [S] | 11+ | 8–15 min flat-vector animation, recurring bird motif | Big ideas and existential science; very high production value; low cadence |
| Peekaboo Kidz (Dr. Binocs) | ~7.6–7.7M, +70K/30d (vidIQ, Jul 2026) [S] | 5–10 | 3–6 min 2D cartoon with a recurring host character | Character-led science Q&A at high volume; the closest structural analog |
| SciShow Kids | ~1.4–1.7M [S] | 4–9 | Live host plus animation | Trusted (Complexly), younger skew; slower cadence |
| Crash Course Kids | (not found) | 8–12 | 3–6 min host plus animation; historically bi-weekly | Curriculum (NGSS) science; series appears complete [S] |
| Free School | (not found) | 6–12 | Narrated stills/animation, 5–15 min | Arts, history, science; low-cost format |
| Homeschool Pop | (not found) | 5–10 | Animation plus narration | Homeschool curriculum |
| Operation Ouch (CBBC) | — | 7–12 | Live-action doctors plus experiments | Human body, broadcaster-backed |
| Mark Rober | very large | 9+ | Live-action engineering builds | Inspiration and engineering, not animation |

Gaps to fill in Phase 1 using the YouTube Data API `channels.list` once an API key is available:
- exact subscriber and view counts;
- upload frequency (videos per 30 days);
- median duration;
- views-per-video distribution.

This makes the analysis reproducible rather than tracker-dependent.

## 2. Pattern analysis

### What winners share [A, from observation of formats listed above]
1. **A recognisable recurring guide or motif.** Dr. Binocs, Kurzgesagt's birds, the SciShow host. A character creates habit and trust.
2. **One question per video.** Titles are phrased as the kid's own question ("Why do we…?").
3. **Visual explanation, not decoration.** Diagrams, cutaways and scale comparisons do the teaching.
4. **Consistent visual system.** Palette, typography and thumbnail grammar are identifiable at thumbnail size.

### Where they are weak (our openings)
| Weakness | Who | Opportunity |
|---|---|---|
| Skews too young (5–9) for 10–12-year-olds | Peekaboo Kidz, SciShow Kids, Homeschool Pop | Pitch at 8–12: slightly faster pace, real numbers, "you'll impress your teacher" facts |
| Skews too old or abstract and occasionally scary (existential themes) | Kurzgesagt, TED-Ed | Same wonder, kid-safe framing, a protagonist kids identify with |
| Lecture format; host explains *at* the viewer | Many explainers | **Adventure format**: the character doesn't know the answer and discovers it alongside the viewer |
| Low cadence: the high-quality channels publish monthly | Kurzgesagt, TED-Ed | Reliable cadence (start at 3/week and move to daily only if quality holds) |
| Sources rarely shown on screen or in the description | Most | **Visible source list** in every description, as a parent and teacher trust signal |
| AI-generated kids channels: inconsistent characters, garbled text, factual errors (the NYT/Feb 2026 terminations) | AI "slop" farms | Show that an AI-assisted pipeline can be *more* accurate and consistent than human-only budget channels |

## 3. Differentiation statement

> **For curious 8–12-year-olds, [Channel] is the animated adventure series where a young explorer and their Discovery Compass chase one big question per episode, so learning feels like a quest, not a lesson. Unlike lecture-style explainers, every episode is a story; unlike AI content farms, every fact is source-checked and shown.**

## 4. Thumbnail and title grammar (to be validated by our own CTR data)

Observed conventions [A]:
- one focal object, oversized, high contrast;
- the character's face showing a strong emotion (surprise or wonder);
- 0–3 words of text;
- the question in the title, not the thumbnail.

For MFK, titles must avoid manipulative urgency ("You WON'T believe…") because of the quality principles and our brand promise.

## 5. Ethical guardrails for competitive work
- No reuse of competitor character traits that are distinctive (e.g. a scientist with binocular-glasses, bird mascots).
- Topic overlap is fine (facts aren't ownable). Script structure, jokes, specific analogies and visual metaphors must be original.
- The Topic Selection Agent records the top 5 existing videos per topic. The Script Agent receives only *our* research brief, never competitor transcripts, to avoid unconscious copying.
