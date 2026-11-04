"""LLM provider interface. Stages depend on this, never on a concrete vendor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

from factory.pipeline.stage import PermanentStageError, RetryableStageError

T = TypeVar("T", bound=BaseModel)

UsageCallback = Callable[..., None]


class Tier(StrEnum):
    HIGH = "high"      # script, fact-check adjudication, final content QA
    MEDIUM = "medium"  # storyboard, visual plan, research
    LOW = "low"        # classification, tags, cheap validation


class LLMError(Exception):
    pass


class LLMRetryableError(LLMError, RetryableStageError):
    """Timeouts, rate limits, overload, malformed output. Retried with backoff."""


class LLMPermanentError(LLMError, PermanentStageError):
    """Bad request, auth problems, refusals. Not retried."""


class LLMQuotaExceeded(LLMRetryableError):
    """Our own daily call cap for the subscription was reached."""


@dataclass(frozen=True)
class LLMRequest(Generic[T]):
    prompt: str
    system: str | None = None
    schema: type[T] | None = None
    tier: Tier = Tier.MEDIUM
    # Built-in tools the model may use, e.g. ("WebSearch", "WebFetch") for research.
    tools: tuple[str, ...] = ()
    agent: str = "unknown"  # for metering / logs


@dataclass(frozen=True)
class LLMResponse(Generic[T]):
    text: str
    data: T | None
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0  # equivalent API cost reported by the provider
    duration_ms: int | None = None
    num_turns: int | None = None
    request_hash: str | None = None


class LLMProvider(Protocol):
    name: str

    def complete(
        self, request: LLMRequest[T], record_usage: UsageCallback | None = None
    ) -> LLMResponse[T]: ...
