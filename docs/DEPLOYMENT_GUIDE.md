# Deployment Guide (draft: finalised once M1 code exists)

## Target environment
- Linux (Ubuntu 24.04) VPS or owner machine: **8 vCPU, 16 GB RAM, 200 GB SSD** recommended (4 vCPU works but renders slower).
- Open outbound HTTPS to:
  - api.anthropic.com
  - generativelanguage.googleapis.com
  - api.openai.com
  - api.elevenlabs.io
  - www.googleapis.com / youtube.googleapis.com / youtubeanalytics.googleapis.com / youtubereporting.googleapis.com
  - oauth2.googleapis.com
- Note: the Claude Code cloud session used for development blocks these hosts by default. Run production elsewhere, or extend that environment's network allowlist for live tests.

## Dependencies
- Python 3.12+ with `uv`; Node 22 LTS; FFmpeg ≥ 6.1; PostgreSQL 16; Chromium (Remotion downloads its headless shell, or set `REMOTION_CHROME` to a system Chromium); fonts from `brand/fonts/` (OFL licences included).
- Optional: Redis (not needed in v1), Blender 4.x headless (only if the 3D pose-library rig is chosen).

## Setup (planned commands)
```bash
git clone https://github.com/chocolatecodelab/ai-motion-graphic-kids-youtube && cd ai-motion-graphic-kids-youtube
uv sync                                  # python deps from lockfile
(cd remotion && npm ci)                  # remotion deps
cp .env.example .env                     # fill secrets
createdb factory && uv run alembic upgrade head
uv run factory auth youtube              # one-time OAuth in a browser (owner)
uv run factory doctor                    # checks ffmpeg, node, chrome, db, keys, quotas, disk
```

## Services (systemd)
| Unit | Command | Notes |
|---|---|---|
| `factory-worker@llm` | `factory worker --lane llm --concurrency 4` | |
| `factory-worker@media` | `factory worker --lane media --concurrency 2` | |
| `factory-worker@render` | `factory worker --lane render --concurrency 1` | Owns the Remotion render-server |
| `factory-worker@publish` | `factory worker --lane publish --concurrency 1` | |
| `factory-scheduler` | `factory scheduler` | APScheduler, TZ from settings |
| `factory-studio` | `uvicorn factory.studio:app --host 127.0.0.1 --port 8080` | Behind Caddy/Nginx with basic auth or Tailscale. **Never expose without auth** |

Docker Compose is provided as an alternative (postgres, studio, worker, scheduler).

## Secrets
- Source of truth is `.env` (mode 600), not committed. `.env.example` lists every key.
- `TOKEN_ENCRYPTION_KEY` (Fernet) encrypts OAuth tokens in the DB. Back it up separately from DB backups.
- Rotate API keys quarterly. `factory doctor` reports key presence, never key values.

## Backups & recovery
- Nightly `pg_dump` (14 daily + 8 weekly copies) plus `content/` and `library/` rsync/rclone to S3-compatible storage.
- Monthly restore drill to a scratch DB.
- Worker crash: jobs left in `running` with a stale `locked_at` (> lane timeout) are re-queued automatically. Uploads resume from the stored resumable session URI.

## Monitoring & alerting
- `factory doctor --cron` hourly. Alerts on:
  - disk > 80%;
  - failed_permanent jobs;
  - budget soft/hard thresholds;
  - OAuth refresh failure;
  - scheduled-but-not-uploaded episode within 12 h of its slot;
  - quota errors.
- Dashboard health panel: last success per stage, queue depth, today's spend.

## Release process
- `main` is protected. Changes go through PRs with CI green.
- Prompt or schema change → bump the agent `version` (invalidates the cache for that stage only).
- Remotion component change → the code hash changes, so only affected scenes re-render.
