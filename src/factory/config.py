"""Application settings loaded from environment variables / .env.

Secrets are held as SecretStr so they never appear in reprs or logs.
Provider defaults follow the free-first stack in docs/DECISIONS.md (D2).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PublicationMode(StrEnum):
    MANUAL = "MANUAL"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FULL_AUTOMATION = "FULL_AUTOMATION"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FACTORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    timezone: str = "Asia/Jakarta"
    content_dir: Path = Path("./content")
    library_dir: Path = Path("./library")
    log_dir: Path = Path("./logs")
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://factory:factory_dev_password@127.0.0.1:25432/factory"

    # --- publication safety (master prompt section 11)
    publication_mode: PublicationMode = PublicationMode.APPROVAL_REQUIRED
    full_automation_enabled: bool = False

    # --- providers (free-first, DECISIONS.md D2)
    llm_provider: str = "claude_cli"  # claude_cli | fake (tests) | anthropic_api (paid, later)
    claude_cli_path: str = "claude"
    # Model alias per tier, passed to `claude -p --model`. Empty = CLI default.
    llm_model_high: str = "opus"     # script, fact-check adjudication, final content QA
    llm_model_medium: str = "sonnet"  # storyboard, visual plan, research
    llm_model_low: str = "haiku"     # classification, SEO tags, cheap validation
    llm_timeout_s: int = Field(default=900, ge=10)

    # Rendering: preview = 960x540 quick review clips; final = 1920x1080 for publishing.
    render_quality: Literal["preview", "final"] = "preview"

    # Voices chosen by the owner in the 2026-11-04 bake-off (DECISIONS.md).
    tts_provider: str = "kokoro"
    tts_hero_voice: str = "af_heart"      # Arka
    tts_hero_speed: float = Field(default=1.0, gt=0.5, lt=2.0)
    tts_companion_voice: str = "af_sky"   # Lipa
    tts_companion_speed: float = Field(default=1.1, gt=0.5, lt=2.0)

    # --- budgets (USD; soft = notify, hard = pause queue). Marginal cost is ~$0 on the
    # free-first stack; these guard any paid adapter that gets switched on.
    budget_episode_soft_usd: float = Field(default=10, ge=0)
    budget_episode_hard_usd: float = Field(default=25, ge=0)
    budget_daily_soft_usd: float = Field(default=15, ge=0)
    budget_daily_hard_usd: float = Field(default=40, ge=0)
    budget_monthly_soft_usd: float = Field(default=400, ge=0)
    budget_monthly_hard_usd: float = Field(default=700, ge=0)
    # Subscription usage guard for `claude -p` calls (DECISIONS.md: budgets track usage).
    llm_max_calls_per_day: int = Field(default=60, ge=1)

    # --- optional paid adapters (vendor-standard names, no FACTORY_ prefix)
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY")
    )
    google_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_API_KEY")
    )
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    elevenlabs_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ELEVENLABS_API_KEY")
    )

    # --- YouTube / notifications (later milestones)
    youtube_client_secrets_file: Path = Path("./secrets/client_secret.json")
    token_encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("TOKEN_ENCRYPTION_KEY", "FACTORY_TOKEN_ENCRYPTION_KEY"),
    )
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {v!r}") from exc
        return v

    @field_validator(
        "anthropic_api_key",
        "google_api_key",
        "openai_api_key",
        "elevenlabs_api_key",
        "token_encryption_key",
        "telegram_bot_token",
        "telegram_chat_id",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v

    @model_validator(mode="after")
    def _check_consistency(self) -> Settings:
        # Full automation must be explicitly enabled by the owner.
        if (
            self.publication_mode is PublicationMode.FULL_AUTOMATION
            and not self.full_automation_enabled
        ):
            raise ValueError(
                "publication_mode=FULL_AUTOMATION requires FACTORY_FULL_AUTOMATION_ENABLED=true"
            )
        for scope in ("episode", "daily", "monthly"):
            soft = getattr(self, f"budget_{scope}_soft_usd")
            hard = getattr(self, f"budget_{scope}_hard_usd")
            if soft > hard:
                raise ValueError(f"budget_{scope}: soft limit ({soft}) exceeds hard ({hard})")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def credential_status(self) -> dict[str, bool]:
        """Which optional credentials are configured. Names only - never values."""
        return {
            "YOUTUBE_CLIENT_SECRETS": self.youtube_client_secrets_file.is_file(),
            "TOKEN_ENCRYPTION_KEY": self.token_encryption_key is not None,
            "TELEGRAM": self.telegram_bot_token is not None and bool(self.telegram_chat_id),
            "ANTHROPIC_API_KEY (optional)": self.anthropic_api_key is not None,
            "GOOGLE_API_KEY (optional)": self.google_api_key is not None,
            "OPENAI_API_KEY (optional)": self.openai_api_key is not None,
            "ELEVENLABS_API_KEY (optional)": self.elevenlabs_api_key is not None,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
