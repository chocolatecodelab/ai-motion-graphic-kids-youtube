"""Structured logging with secret redaction.

Every log event passes through `redact_secrets` before rendering, so API keys,
OAuth tokens and Authorization headers never reach the console or log files.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog

REDACTED = "***REDACTED***"

_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|cookie|credential|fernet)",
    re.IGNORECASE,
)

# Value patterns for secrets that end up inside free text (error messages, URLs).
_SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),          # Anthropic
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),              # OpenAI-style
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),             # Google API key
    re.compile(r"ya29\.[0-9A-Za-z_\-\.]{20,}"),         # Google OAuth access token
    re.compile(r"1//[0-9A-Za-z_\-]{20,}"),              # Google OAuth refresh token
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.=]{10,}"),  # Authorization: Bearer ...
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{30,}\b"),    # Telegram bot token
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),     # user:password@ in URLs
]


def redact_text(text: str) -> str:
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def _redact(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {k: _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_redact(v) for v in value)
    return value


def redact_secrets(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return {k: (_redact(v, k) if k != "event" else _redact(v)) for k, v in event_dict.items()}


def configure_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure structlog: human-readable console, optional JSON-lines file."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level.upper(), handlers=handlers, format="%(message)s", force=True)

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if log_file is not None
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            redact_secrets,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
