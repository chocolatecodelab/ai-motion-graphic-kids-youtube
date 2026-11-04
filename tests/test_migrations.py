"""Alembic migrations must upgrade/downgrade cleanly and match the ORM models."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from factory.db import Base

ROOT = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    return cfg


def test_upgrade_downgrade_sqlite(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {"episodes", "production_jobs", "model_usage", "visual_assets"} <= tables

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"

    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


@pytest.mark.integration
def test_postgres_schema_matches_models() -> None:
    """Runs against the docker compose Postgres when FACTORY_TEST_PG_URL is set."""
    url = os.environ.get("FACTORY_TEST_PG_URL")
    if not url:
        pytest.skip("FACTORY_TEST_PG_URL not set")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], f"Postgres schema differs from models: {diff}"
