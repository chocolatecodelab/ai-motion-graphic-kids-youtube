# API Integration Plan

Rule: read the official docs before implementing each integration. Record the doc URL and the date read in code comments. Every integration ships with a fake provider for tests and a recorded-fixture contract test.

## 1. Anthropic (Claude)
- SDK: `anthropic` (Python). Models via config tiers:
  - `reasoning=claude-opus-5-5`
  - `standard=claude-sonnet-5-5`
  - `fast=claude-haiku-5-5`
- Features used:
  - structured outputs (`output_config.format`);
  - adaptive thinking with explicit `output_config.effort`;
  - prompt caching (stable prefix);
  - Message Batches (nightly research);
  - server tools `web_search_20260209` / `web_fetch_20260209` with domain allowlists.
- Handle:
  - `stop_reason == "refusal"` (server-side `fallbacks` per current SDK guidance);
  - `max_tokens`;
  - 429/5xx retries (SDK default 2, plus our job-level retry).
- Env: `ANTHROPIC_API_KEY`.

## 2. Google Gemini (images; optional LLM)
- SDK: `google-genai`. Models via config (`IMAGE_MODEL_DEFAULT`).
- Batch mode for non-urgent images. Store `provider/model/prompt/refs/params`.
- Env: `GEMINI_API_KEY`.

## 3. OpenAI (images, optional TTS/LLM fallback)
- SDK: `openai`. Image model via config (note: GPT Image 1.5 and 1-mini are reportedly retiring 2026-12-01, so do not hardcode).
- Env: `OPENAI_API_KEY`.

## 4. ElevenLabs (TTS)
- REST / official SDK. Use the endpoint variant that returns character-level timestamps.
- Designed voices only (no real-person cloning).
- Plan must include commercial rights. Store the plan tier with each audio asset.
- Env: `ELEVENLABS_API_KEY`, voice IDs in `character_versions`.

## 5. Google Cloud TTS (fallback)
- `google-cloud-texttospeech`, Chirp 3 HD voices. Env: service-account JSON path.

## 6. YouTube Data API v3 + OAuth 2.0
**Scopes (minimum):**
- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube` (thumbnails.set, captions.insert, videos.update)
- `https://www.googleapis.com/auth/yt-analytics.readonly`

Re-verify the minimal scope set for `thumbnails.set` and `captions` in the docs.

**Auth flow:**
- One-time installed-app OAuth (`factory auth youtube`) run by the owner on a machine with a browser.
- The refresh token is stored encrypted (`oauth_credentials`), and access tokens are refreshed automatically.
- Token values are never logged.

**Calls & quota** (default 10,000 units/day):

| Call | Purpose | Units |
|---|---|---|
| `videos.insert` (resumable) | Upload | 100 per current docs (older docs: 1,600); **budget 1,600 to be safe** |
| `thumbnails.set` | Custom thumbnail | 50 |
| `captions.insert` | en captions | 400 |
| `videos.list` | Verify / processing status | 1 |
| `videos.update` | Fix metadata | 50 |
| `channels.list` / `playlistItems.insert` | Channel info / add to series playlist | 1 / 50 |

Daily worst case is about 2,200 units, well inside quota.

**`status` on insert:**
- `privacyStatus: "private"`
- `publishAt: <RFC3339 slot>` (only valid with private)
- `selfDeclaredMadeForKids: true`
- `containsSyntheticMedia: <policy>` (see §8)
- `license: youtube`
- `embeddable: true`

**Critical blockers (start now, lead time of weeks):**
1. **API compliance audit.** Uploads from unverified projects created after 2020-07-28 are locked to private. Until the audit passes, APPROVAL_REQUIRED works as "upload private → owner publishes manually in YouTube Studio". Scheduling via `publishAt` will not make the video public.
2. **OAuth consent "In production" + verification** for sensitive scopes. In Testing mode, refresh tokens expire after 7 days, which breaks unattended uploads.
3. **Channel verification** (phone) for custom thumbnails.

## 7. YouTube Analytics API + Reporting API
- Analytics API `reports.query` (`ids=channel==MINE`):
  - metrics `views, estimatedMinutesWatched, averageViewDuration, averageViewPercentage, subscribersGained`;
  - retention via `dimensions=elapsedVideoTimeRatio` with `metrics=audienceWatchRatio,relativeRetentionPerformance` filtered by `video==ID`.
- Reporting API: create a job for the reach report type (thumbnail impressions/CTR). It is async and reports appear about 24–48 h later. **Verify** the report type name and availability for MFK channels.
- Data is delayed 24–72 h, so snapshots run at d1/d3/d7/d28.

## 8. Policy decisions encoded in config
| Setting | Default | Note |
|---|---|---|
| `MADE_FOR_KIDS` | `true` (locked) | Audience is 8–12, under 13 (COPPA). Changing it requires a code change plus documented legal review |
| `CONTAINS_SYNTHETIC_MEDIA` | `false` + description disclosure line | YouTube's A/S label targets *realistic* altered content. Stylised animation is likely out of scope, but kids-AI scrutiny is high, so we disclose AI assistance in the description. **Owner decision; re-check YouTube policy text before launch** |
| `CATEGORY_ID` | `27` (Education) | |
| `DEFAULT_LANGUAGE` | `en` | |
| `PUBLICATION_MODE` | `APPROVAL_REQUIRED` | FULL_AUTOMATION requires an owner action + trial pass record |

## 9. Publication modes (behaviour)
| Mode | After QA pass | Upload | Publish |
|---|---|---|---|
| MANUAL | Build an upload package (MP4, thumbnail, SRT, metadata.json, checklist) | Human | Human |
| APPROVAL_REQUIRED | Notify the owner (email/Telegram) with a dashboard link | Auto as **private** after final approval | `publishAt` set after explicit approval (pre-audit: owner publishes in Studio) |
| FULL_AUTOMATION | All gates automated | Auto private + `publishAt` | Automatic; any critical QA fail blocks; owner notified of each publish |

## 10. Notifications
Email (SMTP) or Telegram bot for approvals, failures, budget thresholds and published confirmations. Env: `SMTP_*` or `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Notifications contain no tokens and no child data (we collect none).
