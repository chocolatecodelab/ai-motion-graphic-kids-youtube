"""Deterministic fake LLM for tests and offline development."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any

from factory.providers.llm.base import LLMRequest, LLMResponse, T, UsageCallback

Responder = Callable[[LLMRequest[Any]], Any]


class FakeLLM:
    """Returns queued outputs (dicts for schema requests, strings otherwise), or the
    output of `responder`. Queued exceptions are raised, to test error handling."""

    name = "fake"

    def __init__(self, outputs: list[Any] | None = None, responder: Responder | None = None):
        self.outputs: deque[Any] = deque(outputs or [])
        self.responder = responder
        self.requests: list[LLMRequest[Any]] = []

    def complete(
        self, request: LLMRequest[T], record_usage: UsageCallback | None = None
    ) -> LLMResponse[T]:
        self.requests.append(request)
        out = self.outputs.popleft() if self.outputs else (
            self.responder(request) if self.responder else ""
        )
        if isinstance(out, BaseException):
            raise out
        if record_usage is not None:
            record_usage(provider=self.name, model="fake", operation="messages",
                         units={"agent": request.agent}, cost_usd=0)
        data = request.schema.model_validate(out) if request.schema is not None else None
        return LLMResponse(text=out if isinstance(out, str) else "", data=data, model="fake")
