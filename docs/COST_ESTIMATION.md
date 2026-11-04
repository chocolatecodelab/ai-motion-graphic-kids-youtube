# Cost Estimation (summary)

Full derivation: [research/production-cost-analysis.md](research/production-cost-analysis.md). Figures are estimates until M1 measures real usage.

| Metric | Estimate |
|---|---|
| Variable cost per 6-min episode | **$4.50 – $20.50** (target < $8 once the asset library matures) |
| LLM share | $2.30 – $5.40 |
| Images + thumbnails | $1.40 – $13.30 (largest swing) |
| Voice-over | $0.80 – $2.00 (~$0.03–$0.12 per VO minute) |
| Render | $0 marginal (owned CPU); +$0.01/render if a Remotion Automators licence applies |
| Fixed monthly | $25 – $330 (host, TTS plan, music library, Remotion licence if >3 employees, backups) |
| **Monthly at 30 episodes** | **≈ $190 (lean) · ≈ $450 (expected) · ≈ $930 (heavy)** |
| Storage | ~15 GB/month retained + ~100 GB rolling working set |
| Render time | ~10–35 min per episode (verify in M1) |
| Human time (APPROVAL_REQUIRED) | 20–40 min/episode (main bottleneck at daily cadence) |

## Budget configuration (initial proposal; owner to confirm)
```
BUDGET_EPISODE_USD_SOFT=10   BUDGET_EPISODE_USD_HARD=25
BUDGET_DAILY_USD_SOFT=15     BUDGET_DAILY_USD_HARD=40
BUDGET_MONTHLY_USD_SOFT=400  BUDGET_MONTHLY_USD_HARD=700
```
Hard limits pause the queue. Soft limits notify.

## Revenue reality check
MFK (required for an 8–12 audience) runs contextual ads only. Third-party reports suggest RPMs 50–80% below general content (anecdotal). At an expected ~$450/month operating cost, ad revenue alone needs substantial view volume. Plan for diversification (sponsorships that comply with kids-ad rules, licensing to schools/edtech).
