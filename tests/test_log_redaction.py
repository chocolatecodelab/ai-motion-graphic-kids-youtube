from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.log import REDACTED, configure_logging, get_logger, redact_secrets, redact_text


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789",
        "sk-proj-abcdefghijklmnopqrstuvwxyz012345",
        "AIzaSyA1234567890abcdefghijklmnopqrstu",
        "ya29.a0AfH6SMBabcdefghijklmnopqrstuvwxyz",
        "1//0gabcdefghijklmnopqrstuvwxyz0123",
        "Bearer abcdefghijklmnop.qrstuvwxyz",
        "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
    ],
)
def test_secret_values_redacted_in_text(secret: str) -> None:
    out = redact_text(f"request failed with {secret} attached")
    assert secret not in out
    assert REDACTED in out


def test_url_credentials_redacted() -> None:
    out = redact_text("postgresql+psycopg://factory:hunter2@127.0.0.1:25432/factory")
    assert "hunter2" not in out
    assert "127.0.0.1:25432/factory" in out


def test_sensitive_keys_redacted_recursively() -> None:
    event = {
        "event": "upload",
        "api_key": "plain-value",
        "headers": {"Authorization": "xyz", "Content-Type": "video/mp4"},
        "items": [{"refresh_token": "abc"}],
        "video_id": "dQw4w9WgXcQ",
    }
    out = redact_secrets(None, "info", event)
    assert out["api_key"] == REDACTED
    assert out["headers"]["Authorization"] == REDACTED
    assert out["headers"]["Content-Type"] == "video/mp4"
    assert out["items"][0]["refresh_token"] == REDACTED
    assert out["video_id"] == "dQw4w9WgXcQ"


def test_file_log_never_contains_secret(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    configure_logging("INFO", log_file=log_file)
    get_logger("test").info("calling provider", token="sk-ant-api03-SECRETSECRETSECRET1234")
    import logging

    for h in logging.getLogger().handlers:
        h.flush()
    content = log_file.read_text(encoding="utf-8")
    assert "SECRETSECRET" not in content
    record = json.loads(content.strip().splitlines()[-1])
    assert record["token"] == REDACTED
