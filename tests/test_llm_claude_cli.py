"""ClaudeCodeCLIProvider against recorded/simulated CLI output (no real calls),
plus one opt-in live smoke test."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from pydantic import BaseModel

from factory.config import Settings
from factory.pipeline import PermanentStageError, RetryableStageError
from factory.providers.llm import (
    LLMPermanentError,
    LLMQuotaExceeded,
    LLMRequest,
    LLMRetryableError,
    Tier,
)
from factory.providers.llm.claude_cli import ClaudeCodeCLIProvider
from factory.providers.llm.fake import FakeLLM


class Answer(BaseModel):
    answer: str
    confidence: float


# Shape recorded from a real `claude -p --output-format json --json-schema ...` call (2026-11-04).
RECORDED_OK = {
    "type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
    "duration_ms": 5103, "num_turns": 2, "total_cost_usd": 0.000839,
    "result": '{"answer":"Air bounces blue light around the most.","confidence":0.97}',
    "structured_output": {"answer": "Air bounces blue light around the most.",
                          "confidence": 0.97},
    "usage": {"input_tokens": 2, "output_tokens": 220, "cache_read_input_tokens": 0,
              "cache_creation_input_tokens": 3644, "server_tool_use": {"web_search_requests": 0}},
    "modelUsage": {"claude-haiku-5-5": {}},
}


class Recorder:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr
        self.calls: list[tuple[list[str], str, Path]] = []

    def __call__(self, args, stdin, cwd, timeout):  # type: ignore[no-untyped-def]
        self.calls.append((args, stdin, cwd))
        assert (cwd / "system.md").exists() or "--system-prompt-file" not in args
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)


def provider(runner, **settings_kw) -> ClaudeCodeCLIProvider:  # type: ignore[no-untyped-def]
    return ClaudeCodeCLIProvider(Settings(**settings_kw), runner=runner)


def test_structured_success_and_metering() -> None:
    rec = Recorder(json.dumps(RECORDED_OK))
    usage: list[dict] = []
    resp = provider(rec).complete(
        LLMRequest(prompt="Why is the sky blue?", system="You write for kids 8-12.",
                   schema=Answer, tier=Tier.LOW, agent="smoke"),
        record_usage=lambda **kw: usage.append(kw),
    )
    assert isinstance(resp.data, Answer) and resp.data.confidence == 0.97
    assert resp.model == "claude-haiku-5-5"
    args, stdin, _ = rec.calls[0]
    assert stdin == "Why is the sky blue?"  # prompt via stdin, not argv
    for flag in ("--restricted", "--strict-mcp-config", "--no-session-persistence",
                 "--json-schema", "--system-prompt-file"):
        assert flag in args
    assert args[args.index("--tools") + 1] == ""  # no tools unless requested
    assert args[args.index("--model") + 1] == "haiku"
    assert usage[0]["provider"] == "claude_cli"
    assert usage[0]["units"]["output_tokens"] == 220
    assert usage[0]["cost_usd"] == pytest.approx(0.000839)


def test_research_tools_are_passed_explicitly() -> None:
    rec = Recorder(json.dumps({**RECORDED_OK, "structured_output": None}))
    provider(rec).complete(LLMRequest(prompt="x", tools=("WebSearch", "WebFetch")))
    args = rec.calls[0][0]
    assert args[args.index("--tools") + 1] == "WebSearch,WebFetch"


@pytest.mark.parametrize(
    ("payload", "rc", "error"),
    [
        ({**RECORDED_OK, "is_error": True, "api_error_status": 529, "result": "Overloaded"}, 1,
         LLMRetryableError),
        ({**RECORDED_OK, "is_error": True, "api_error_status": 400, "result": "bad request"}, 1,
         LLMPermanentError),
        ({**RECORDED_OK, "is_error": True, "subtype": "error", "result": "Usage limit reached,"
          " try again later"}, 1, LLMRetryableError),
    ],
)
def test_error_mapping(payload: dict, rc: int, error: type[Exception]) -> None:
    with pytest.raises(error):
        provider(Recorder(json.dumps(payload), returncode=rc)).complete(LLMRequest(prompt="x"))


def test_llm_errors_are_stage_errors() -> None:
    # Stages can let provider errors propagate; the runner maps them to retry/permanent.
    assert issubclass(LLMRetryableError, RetryableStageError)
    assert issubclass(LLMPermanentError, PermanentStageError)


def test_non_json_output() -> None:
    with pytest.raises(LLMPermanentError, match="exited 2"):
        provider(Recorder("", returncode=2, stderr="error: unknown option")).complete(
            LLMRequest(prompt="x"))
    with pytest.raises(LLMRetryableError):
        provider(Recorder("", returncode=1, stderr="Request timed out")).complete(
            LLMRequest(prompt="x"))


def test_invalid_structured_output_is_retryable() -> None:
    bad = {**RECORDED_OK, "structured_output": {"answer": "x"}}  # missing confidence
    with pytest.raises(LLMRetryableError, match="validation"):
        provider(Recorder(json.dumps(bad))).complete(LLMRequest(prompt="x", schema=Answer))


def test_timeout_is_retryable() -> None:
    def slow(args, stdin, cwd, timeout):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(args, timeout)

    with pytest.raises(LLMRetryableError, match="timed out"):
        provider(slow).complete(LLMRequest(prompt="x"))


def test_daily_cap_blocks_before_calling() -> None:
    rec = Recorder(json.dumps(RECORDED_OK))
    p = ClaudeCodeCLIProvider(Settings(llm_max_calls_per_day=5), runner=rec,
                              calls_last_24h=lambda: 5)
    with pytest.raises(LLMQuotaExceeded):
        p.complete(LLMRequest(prompt="x"))
    assert rec.calls == []


def test_fake_llm_validates_schema() -> None:
    fake = FakeLLM([{"answer": "blue", "confidence": 1.0}, LLMRetryableError("boom")])
    assert fake.complete(LLMRequest(prompt="q", schema=Answer)).data == Answer(
        answer="blue", confidence=1.0)
    with pytest.raises(LLMRetryableError):
        fake.complete(LLMRequest(prompt="q"))


@pytest.mark.live
def test_live_claude_cli_smoke() -> None:
    """Real `claude -p` call on the owner's subscription. Opt in: FACTORY_TEST_LIVE_LLM=1."""
    if os.environ.get("FACTORY_TEST_LIVE_LLM") != "1":
        pytest.skip("set FACTORY_TEST_LIVE_LLM=1 to run")
    resp = ClaudeCodeCLIProvider(Settings()).complete(
        LLMRequest(prompt="In one sentence for a 9-year-old: why is the sky blue?",
                   system="You are a friendly science explainer for kids aged 8-12.",
                   schema=Answer, tier=Tier.LOW, agent="live-smoke")
    )
    assert resp.data is not None and len(resp.data.answer) > 10
    assert 0 <= resp.data.confidence <= 1
