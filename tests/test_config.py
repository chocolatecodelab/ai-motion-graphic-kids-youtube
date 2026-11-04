from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.config import PublicationMode, Settings


def test_defaults_are_safe() -> None:
    s = Settings()
    assert s.publication_mode is PublicationMode.APPROVAL_REQUIRED
    assert s.full_automation_enabled is False
    assert s.llm_provider == "claude_cli"
    assert s.tts_provider == "kokoro"
    assert s.timezone == "Asia/Jakarta"


def test_full_automation_requires_explicit_enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_PUBLICATION_MODE", "FULL_AUTOMATION")
    with pytest.raises(ValidationError, match="FULL_AUTOMATION_ENABLED"):
        Settings()
    monkeypatch.setenv("FACTORY_FULL_AUTOMATION_ENABLED", "true")
    assert Settings().publication_mode is PublicationMode.FULL_AUTOMATION


def test_invalid_timezone_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_TIMEZONE", "Mars/Olympus_Mons")
    with pytest.raises(ValidationError, match="Unknown timezone"):
        Settings()


def test_soft_budget_cannot_exceed_hard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_BUDGET_DAILY_SOFT_USD", "50")
    monkeypatch.setenv("FACTORY_BUDGET_DAILY_HARD_USD", "40")
    with pytest.raises(ValidationError, match="budget_daily"):
        Settings()


def test_blank_keys_are_none_and_secrets_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyTESTVALUE0000000000000000000000")
    s = Settings()
    assert s.anthropic_api_key is None
    assert s.google_api_key is not None
    assert "AIza" not in repr(s)
    status = s.credential_status()
    assert status["GOOGLE_API_KEY (optional)"] is True
    assert all(isinstance(v, bool) for v in status.values())
