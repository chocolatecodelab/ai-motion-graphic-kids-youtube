"""Environment health checks (`factory doctor`).

Each check returns a CheckResult; none of them prints secrets.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from factory.config import PublicationMode, Settings


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str


def _run_version(cmd: list[str], timeout: float = 15) -> str | None:
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or out.stderr).strip()
    return text.splitlines()[0] if text else None


def _major(version_line: str) -> int | None:
    m = re.search(r"(\d+)\.(\d+)", version_line)
    return int(m.group(1)) if m else None


def check_python() -> CheckResult:
    v = sys.version_info
    ok = (v.major, v.minor) == (3, 12)
    return CheckResult(
        "python", Status.OK if ok else Status.FAIL, f"{v.major}.{v.minor}.{v.micro} (need 3.12)"
    )


def check_node() -> CheckResult:
    line = _run_version(["node", "--version"])
    if line is None:
        return CheckResult("node", Status.FAIL, "not found (needed for Remotion)")
    major = _major(line)
    status = Status.OK if major is not None and major >= 20 else Status.WARN
    return CheckResult("node", status, line)


def check_ffmpeg() -> CheckResult:
    ff = _run_version(["ffmpeg", "-version"])
    fp = _run_version(["ffprobe", "-version"])
    if ff is None or fp is None:
        return CheckResult("ffmpeg", Status.FAIL, "ffmpeg/ffprobe not found on PATH")
    return CheckResult("ffmpeg", Status.OK, ff[:60])


def check_docker() -> CheckResult:
    line = _run_version(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
    if line is None or "error" in line.lower():
        return CheckResult("docker", Status.WARN, "daemon not reachable (needed for Postgres)")
    return CheckResult("docker", Status.OK, f"server {line}")


def check_database(settings: Settings) -> CheckResult:
    from sqlalchemy import create_engine, inspect, text

    try:
        engine = create_engine(settings.database_url, connect_args=_connect_args(settings))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            tables = inspect(conn).get_table_names()
        engine.dispose()
    except Exception as exc:  # noqa: BLE001 - report any connection failure
        return CheckResult("database", Status.FAIL, f"cannot connect: {type(exc).__name__}")
    if "alembic_version" not in tables:
        return CheckResult("database", Status.WARN, "connected, but migrations not applied")
    return CheckResult("database", Status.OK, f"connected, {len(tables)} tables")


def _connect_args(settings: Settings) -> dict[str, object]:
    return {"connect_timeout": 5} if settings.database_url.startswith("postgresql") else {}


def check_directories(settings: Settings) -> CheckResult:
    for d in (settings.content_dir, settings.library_dir, settings.log_dir):
        d.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(settings.content_dir.resolve())
    free_gb = usage.free / 1e9
    status = Status.OK if free_gb >= 50 else Status.WARN
    return CheckResult("storage", status, f"{free_gb:.0f} GB free at {settings.content_dir}")


def check_tts(settings: Settings) -> CheckResult:
    if settings.tts_provider != "kokoro":
        return CheckResult("tts", Status.WARN, f"provider {settings.tts_provider!r} not checked")
    if importlib.util.find_spec("kokoro") is None:
        return CheckResult("tts", Status.WARN, "kokoro not installed (uv sync --extra voice)")
    if not settings.tts_hero_voice:
        return CheckResult("tts", Status.WARN, "kokoro installed; hero voice not chosen yet")
    return CheckResult("tts", Status.OK, f"kokoro, hero voice {settings.tts_hero_voice}")


def check_llm(settings: Settings) -> CheckResult:
    if settings.llm_provider != "claude_cli":
        return CheckResult("llm", Status.WARN, f"provider {settings.llm_provider!r} not checked")
    line = _run_version([settings.claude_cli_path, "--version"], timeout=30)
    if line is None:
        return CheckResult(
            "llm", Status.FAIL, f"Claude Code CLI ({settings.claude_cli_path!r}) not found"
        )
    return CheckResult("llm", Status.OK, f"claude CLI {line}")


def check_publication_safety(settings: Settings) -> CheckResult:
    if settings.publication_mode is PublicationMode.FULL_AUTOMATION:
        return CheckResult("publication", Status.WARN, "FULL_AUTOMATION enabled by owner")
    return CheckResult("publication", Status.OK, settings.publication_mode.value)


def check_credentials(settings: Settings) -> CheckResult:
    status = settings.credential_status()
    present = [k for k, v in status.items() if v]
    missing = [k for k, v in status.items() if not v and "(optional)" not in k]
    # YouTube/notification credentials are only required from M5; report, don't fail.
    detail = f"present: {', '.join(present) or 'none'} | missing: {', '.join(missing) or 'none'}"
    return CheckResult("credentials", Status.OK if not missing else Status.WARN, detail)


def run_all(settings: Settings) -> list[CheckResult]:
    checks: list[Callable[[], CheckResult]] = [
        check_python,
        check_node,
        check_ffmpeg,
        check_docker,
        lambda: check_database(settings),
        lambda: check_directories(settings),
        lambda: check_llm(settings),
        lambda: check_tts(settings),
        lambda: check_publication_safety(settings),
        lambda: check_credentials(settings),
    ]
    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as exc:  # noqa: BLE001 - a broken check must not crash doctor
            results.append(CheckResult(getattr(check, "__name__", "check"), Status.FAIL, repr(exc)))
    return results


def remotion_project_present(root: Path = Path("remotion")) -> bool:
    return (root / "package.json").is_file()
