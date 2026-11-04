"""LLM providers. Use `get_llm()` so the provider comes from config."""

from __future__ import annotations

from factory.config import Settings
from factory.providers.llm.base import (
    LLMError,
    LLMPermanentError,
    LLMProvider,
    LLMQuotaExceeded,
    LLMRequest,
    LLMResponse,
    LLMRetryableError,
    Tier,
)


def get_llm(settings: Settings, session_scope=None) -> LLMProvider:  # type: ignore[no-untyped-def]
    if settings.llm_provider == "claude_cli":
        from factory.providers.llm.claude_cli import PROVIDER, ClaudeCodeCLIProvider

        counter = None
        if session_scope is not None:
            from factory.metering import calls_last_24h

            def counter() -> int:
                with session_scope() as s:
                    return calls_last_24h(s, PROVIDER)

        return ClaudeCodeCLIProvider(settings, calls_last_24h=counter)
    if settings.llm_provider == "fake":
        from factory.providers.llm.fake import FakeLLM

        return FakeLLM()
    raise ValueError(f"unsupported llm_provider {settings.llm_provider!r}")


__all__ = [
    "LLMError",
    "LLMPermanentError",
    "LLMProvider",
    "LLMQuotaExceeded",
    "LLMRequest",
    "LLMResponse",
    "LLMRetryableError",
    "Tier",
    "get_llm",
]
