"""Claude through the owner's subscription, via headless Claude Code (`claude -p`).

DECISIONS.md D2. Each call runs:
- with `--restricted --strict-mcp-config` and only the tools the stage asks for
  (none by default), in an empty temporary working directory;
- with `--json-schema` when the stage expects structured output; the CLI returns
  `structured_output`, which is validated again here with Pydantic;
- with `--no-session-persistence`, so calls don't pile up as saved sessions.

The prompt goes through stdin and the system prompt through a file, which avoids
Windows' ~32k command-line limit.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from factory.config import Settings
from factory.log import get_logger
from factory.providers.llm.base import (
    LLMPermanentError,
    LLMQuotaExceeded,
    LLMRequest,
    LLMResponse,
    LLMRetryableError,
    T,
    Tier,
    UsageCallback,
)

log = get_logger(__name__)

PROVIDER = "claude_cli"
MAX_SCHEMA_ARG_CHARS = 24_000  # leaves headroom under the Windows command-line limit
RETRYABLE_HTTP = {408, 409, 429, 500, 502, 503, 504, 529}
RETRYABLE_HINTS = ("overloaded", "rate limit", "rate_limit", "timeout", "timed out", "529",
                   "usage limit", "try again")

Runner = Callable[[list[str], str, Path, int], subprocess.CompletedProcess[str]]


def _default_runner(args: list[str], stdin: str, cwd: Path, timeout: int):
    return subprocess.run(
        args, input=stdin, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=cwd, timeout=timeout, check=False,
    )


class ClaudeCodeCLIProvider:
    name = PROVIDER

    def __init__(
        self,
        settings: Settings,
        runner: Runner | None = None,
        calls_last_24h: Callable[[], int] | None = None,
    ):
        self.settings = settings
        self.runner = runner or _default_runner
        self.calls_last_24h = calls_last_24h
        self.models = {
            Tier.HIGH: settings.llm_model_high,
            Tier.MEDIUM: settings.llm_model_medium,
            Tier.LOW: settings.llm_model_low,
        }

    def build_args(self, request: LLMRequest[Any], system_file: Path | None) -> list[str]:
        exe = shutil.which(self.settings.claude_cli_path) or self.settings.claude_cli_path
        args = [exe, "-p", "--output-format", "json", "--no-session-persistence",
                "--restricted", "--strict-mcp-config", "--tools", ",".join(request.tools)]
        model = self.models[request.tier]
        if model:
            args += ["--model", model]
        if system_file is not None:
            args += ["--system-prompt-file", str(system_file)]
        if request.schema is not None:
            schema = json.dumps(request.schema.model_json_schema(), separators=(",", ":"))
            if len(schema) > MAX_SCHEMA_ARG_CHARS:
                raise LLMPermanentError(
                    f"JSON schema for {request.schema.__name__} is {len(schema)} chars; "
                    f"limit {MAX_SCHEMA_ARG_CHARS}. Split the output model."
                )
            args += ["--json-schema", schema]
        return args

    def complete(
        self, request: LLMRequest[T], record_usage: UsageCallback | None = None
    ) -> LLMResponse[T]:
        if self.calls_last_24h is not None:
            used = self.calls_last_24h()
            if used >= self.settings.llm_max_calls_per_day:
                raise LLMQuotaExceeded(
                    f"daily claude -p cap reached ({used}/{self.settings.llm_max_calls_per_day})"
                )

        with tempfile.TemporaryDirectory(prefix="factory-llm-") as tmp:
            cwd = Path(tmp)
            system_file = None
            if request.system:
                system_file = cwd / "system.md"
                system_file.write_text(request.system, encoding="utf-8")
            args = self.build_args(request, system_file)
            req_hash = hashlib.sha256(
                json.dumps([args[1:], request.system, request.prompt]).encode("utf-8")
            ).hexdigest()
            started = time.perf_counter()
            try:
                proc = self.runner(args, request.prompt, cwd, self.settings.llm_timeout_s)
            except subprocess.TimeoutExpired as exc:
                raise LLMRetryableError(
                    f"claude -p timed out after {self.settings.llm_timeout_s}s"
                ) from exc
            except OSError as exc:
                raise LLMPermanentError(f"cannot start Claude Code CLI: {exc}") from exc
            wall_ms = int((time.perf_counter() - started) * 1000)

        payload = self._parse(proc)
        model = next(iter(payload.get("modelUsage") or {}), self.models[request.tier] or "default")
        usage = payload.get("usage") or {}
        units = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "cache_creation": usage.get("cache_creation_input_tokens", 0),
            "num_turns": payload.get("num_turns"),
            "web_search_requests": (usage.get("server_tool_use") or {}).get(
                "web_search_requests", 0
            ),
            "agent": request.agent,
        }
        cost = float(payload.get("total_cost_usd") or 0.0)
        duration = int(payload.get("duration_ms") or wall_ms)
        if record_usage is not None:
            record_usage(provider=PROVIDER, model=model, operation="messages", units=units,
                         cost_usd=cost, request_hash=req_hash, latency_ms=duration)

        data = None
        if request.schema is not None:
            raw = payload.get("structured_output")
            if raw is None:
                raw = _json_or_none(payload.get("result"))
            if raw is None:
                raise LLMRetryableError("no structured output returned")
            try:
                data = request.schema.model_validate(raw)
            except ValidationError as exc:
                raise LLMRetryableError(
                    f"output failed {request.schema.__name__} validation: "
                    f"{exc.error_count()} errors"
                ) from exc

        log.info("llm call", provider=PROVIDER, model=model, agent=request.agent,
                 tokens_in=units["input_tokens"], tokens_out=units["output_tokens"],
                 cost_equiv_usd=cost, duration_ms=duration)
        return LLMResponse(
            text=str(payload.get("result") or ""),
            data=data,
            model=model,
            usage=units,
            cost_usd=cost,
            duration_ms=duration,
            num_turns=payload.get("num_turns"),
            request_hash=req_hash,
        )

    @staticmethod
    def _parse(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        payload = _json_or_none(proc.stdout)
        if not isinstance(payload, dict):
            detail = (proc.stderr or proc.stdout or "").strip()[:500]
            if proc.returncode != 0 and not _looks_retryable(detail):
                raise LLMPermanentError(f"claude -p exited {proc.returncode}: {detail}")
            raise LLMRetryableError(f"claude -p returned non-JSON output: {detail}")
        if payload.get("is_error") or proc.returncode != 0:
            status = payload.get("api_error_status")
            detail = str(payload.get("result") or payload.get("subtype") or "")[:500]
            msg = f"claude -p error (status={status}, subtype={payload.get('subtype')}): {detail}"
            if (isinstance(status, int) and status in RETRYABLE_HTTP) or _looks_retryable(detail):
                raise LLMRetryableError(msg)
            raise LLMPermanentError(msg)
        return payload


def _json_or_none(text: Any) -> Any:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _looks_retryable(detail: str) -> bool:
    low = detail.lower()
    return any(h in low for h in RETRYABLE_HINTS)
