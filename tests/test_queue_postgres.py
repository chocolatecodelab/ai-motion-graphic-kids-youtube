"""SKIP LOCKED claiming on real Postgres: concurrent workers never get the same job.

Runs in a throwaway schema; needs FACTORY_TEST_PG_URL (docker compose Postgres).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from factory.db import Base
from factory.db.models import Channel, Episode, JobStatus, Lane, ProductionJob, Project
from factory.pipeline import queue

pytestmark = pytest.mark.integration


@pytest.fixture
def pg_engine():  # type: ignore[no-untyped-def]
    url = os.environ.get("FACTORY_TEST_PG_URL")
    if not url:
        pytest.skip("FACTORY_TEST_PG_URL not set")
    schema = f"pytest_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def test_concurrent_claims_get_different_jobs(pg_engine) -> None:  # type: ignore[no-untyped-def]
    with Session(pg_engine) as s:
        ch = Channel(name="Explore")
        pr = Project(channel=ch, name="Main Quest")
        ep = Episode(project=pr, number=1, slug="sky")
        s.add_all([ch, pr, ep])
        s.flush()
        for stage in ("research", "topic_selection"):
            s.add(ProductionJob(episode_id=ep.id, stage=stage, lane=Lane.LLM,
                                status=JobStatus.QUEUED))
        s.commit()

    s1, s2 = Session(pg_engine), Session(pg_engine)
    try:
        j1 = queue.claim_next(s1, Lane.LLM, "w1")  # holds its row lock (uncommitted)
        j2 = queue.claim_next(s2, Lane.LLM, "w2")  # must skip the locked row
        j3 = None
        assert j1 is not None and j2 is not None
        assert j1.id != j2.id
        with Session(pg_engine) as s3:
            j3 = queue.claim_next(s3, Lane.LLM, "w3")  # both rows locked -> nothing
        assert j3 is None
        s1.commit()
        s2.commit()
    finally:
        s1.close()
        s2.close()
