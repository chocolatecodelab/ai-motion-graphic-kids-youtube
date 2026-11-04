from __future__ import annotations

import pytest

from factory import doctor
from factory.config import Settings
from factory.doctor import Status


def test_database_check_fails_cleanly_without_server() -> None:
    s = Settings(database_url="postgresql+psycopg://u:p@127.0.0.1:1/none")
    result = doctor.check_database(s)
    assert result.status is Status.FAIL
    assert "p@" not in result.detail  # no credentials echoed


def test_database_check_warns_when_unmigrated(tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = Settings(database_url=f"sqlite+pysqlite:///{(tmp_path / 'x.db').as_posix()}")
    assert doctor.check_database(s).status is Status.WARN


def test_missing_claude_cli_fails() -> None:
    s = Settings(claude_cli_path="definitely-not-a-real-binary-xyz")
    assert doctor.check_llm(s).status is Status.FAIL


def test_credentials_report_names_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "super-secret-fernet-key")
    result = doctor.check_credentials(Settings())
    assert "super-secret" not in result.detail
    assert "TOKEN_ENCRYPTION_KEY" in result.detail


def test_run_all_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> doctor.CheckResult:
        raise RuntimeError("broken check")

    monkeypatch.setattr(doctor, "check_python", boom)
    results = doctor.run_all(Settings(database_url="sqlite+pysqlite:///:memory:"))
    assert any(r.status is Status.FAIL and "broken check" in r.detail for r in results)
