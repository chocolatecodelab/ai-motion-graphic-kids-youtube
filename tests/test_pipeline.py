"""Queue + worker behaviour: DAG order, cache, retries, approval gate, retry/cancel, leases."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from factory.config import PublicationMode, Settings
from factory.db import Base
from factory.db.base import utcnow
from factory.db.models import (
    Channel,
    Episode,
    EpisodeStatus,
    JobStatus,
    Lane,
    ModelUsage,
    ProductionJob,
    Project,
)
from factory.pipeline import (
    PermanentStageError,
    RetryableStageError,
    Stage,
    StageContext,
    StageResult,
    Workflow,
    queue,
)
from factory.pipeline.runner import Worker

CALLS: list[str] = []


class Research(Stage):
    name = "research"
    lane = Lane.LLM

    def run(self, ctx: StageContext) -> StageResult:
        CALLS.append(self.name)
        ctx.record_usage(provider="fake", model="m", operation="messages", units={"n": 1})
        return StageResult({"brief": "sky.json"})


class Script(Stage):
    name = "script"
    lane = Lane.LLM
    depends_on = ("research",)
    approval_modes = frozenset({PublicationMode.APPROVAL_REQUIRED})

    def run(self, ctx: StageContext) -> StageResult:
        CALLS.append(self.name)
        assert ctx.upstream["research"]["brief"] == "sky.json"
        return StageResult({"script": "v1.json"})


class Voice(Stage):
    name = "voice"
    lane = Lane.MEDIA
    depends_on = ("script",)

    def run(self, ctx: StageContext) -> StageResult:
        CALLS.append(self.name)
        return StageResult({"wav": "vo.wav"})


def wf() -> Workflow:
    return Workflow([Research(), Script(), Voice()])


@pytest.fixture
def scope(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'q.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _r):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session_scope() -> Iterator[Session]:
        s = maker()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    CALLS.clear()
    yield session_scope
    engine.dispose()


def _episode(scope, slug: str = "sky") -> uuid.UUID:  # type: ignore[no-untyped-def]
    with scope() as s:
        ch = s.scalar(select(Channel)) or Channel(name="Explore")
        pr = s.scalar(select(Project)) or Project(channel=ch, name="Main Quest")
        n = len(s.scalars(select(Episode)).all()) + 1
        ep = Episode(project=pr, number=n, slug=f"{slug}-{n}")
        s.add_all([ch, pr, ep])
        s.flush()
        queue.enqueue_episode(s, ep.id, wf())
        return ep.id


def _status(scope, ep: uuid.UUID) -> dict[str, JobStatus]:  # type: ignore[no-untyped-def]
    with scope() as s:
        return {j.stage: j.status for j in s.scalars(
            select(ProductionJob).where(ProductionJob.episode_id == ep))}


def _worker(scope, lane: Lane, tmp_path: Path, mode=PublicationMode.MANUAL) -> Worker:  # type: ignore[no-untyped-def]
    settings = Settings(publication_mode=mode, content_dir=tmp_path / "content")
    return Worker(lane, wf(), scope, settings, worker_id=f"test-{lane.value}")


def test_workflow_rejects_cycles_and_unknown_deps() -> None:
    class A(Stage):
        name, lane, depends_on = "a", Lane.LLM, ("b",)

    class B(Stage):
        name, lane, depends_on = "b", Lane.LLM, ("a",)

    with pytest.raises(ValueError, match="cycle"):
        Workflow([A(), B()])
    with pytest.raises(ValueError, match="unknown"):
        Workflow([A()])


def test_enqueue_starts_only_root_stages(scope) -> None:  # type: ignore[no-untyped-def]
    ep = _episode(scope)
    assert _status(scope, ep) == {
        "research": JobStatus.QUEUED, "script": JobStatus.PENDING, "voice": JobStatus.PENDING,
    }
    with scope() as s, pytest.raises(ValueError, match="active jobs"):
        queue.enqueue_episode(s, ep, wf())


def test_full_run_in_manual_mode(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ep = _episode(scope)
    _worker(scope, Lane.LLM, tmp_path).run_until_idle()
    assert CALLS == ["research", "script"]
    assert _status(scope, ep)["voice"] is JobStatus.QUEUED  # promoted, other lane
    _worker(scope, Lane.MEDIA, tmp_path).run_until_idle()
    assert set(_status(scope, ep).values()) == {JobStatus.SUCCEEDED}
    with scope() as s:
        assert s.get(Episode, ep).status is EpisodeStatus.READY
        usage = s.scalars(select(ModelUsage)).all()
        assert len(usage) == 1 and usage[0].episode_id == ep


def test_approval_gate_blocks_downstream(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ep = _episode(scope)
    w = _worker(scope, Lane.LLM, tmp_path, PublicationMode.APPROVAL_REQUIRED)
    w.run_until_idle()
    st = _status(scope, ep)
    assert st["script"] is JobStatus.AWAITING_APPROVAL
    assert st["voice"] is JobStatus.PENDING
    with scope() as s:
        assert s.get(Episode, ep).status is EpisodeStatus.AWAITING_APPROVAL
        queue.approve(s, ep, "script", wf())
    assert _status(scope, ep)["voice"] is JobStatus.QUEUED


def test_cache_hit_skips_rerun(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _episode(scope, "a")
    _worker(scope, Lane.LLM, tmp_path).run_until_idle()
    CALLS.clear()
    _episode(scope, "b")  # identical inputs -> research is a cache hit
    outcomes = _worker(scope, Lane.LLM, tmp_path).run_until_idle()
    research = next(o for o in outcomes if o.stage == "research")
    assert research.cache_hit is True
    assert "research" not in CALLS


def test_retryable_failure_backs_off_then_permanent(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    class Flaky(Research):
        def run(self, ctx: StageContext) -> StageResult:
            raise RetryableStageError("429 rate limited")

    ep = _episode(scope)
    w = Worker(Lane.LLM, Workflow([Flaky(), Script(), Voice()]), scope,
               Settings(content_dir=tmp_path), worker_id="t")
    w.run_once()
    with scope() as s:
        job = s.scalars(select(ProductionJob).where(ProductionJob.stage == "research")).one()
        assert job.status is JobStatus.FAILED_RETRYABLE
        assert job.run_after > utcnow() + timedelta(seconds=50)  # 2^1*30s backoff
        assert w.run_once() is None  # not claimable until run_after
        job.run_after = utcnow()
        job.attempt = job.max_attempts - 1
    w.run_once()
    st = _status(scope, ep)
    assert st["research"] is JobStatus.FAILED_PERMANENT
    with scope() as s:
        assert s.get(Episode, ep).status is EpisodeStatus.FAILED


def test_permanent_error_is_not_retried(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    class Invalid(Research):
        def run(self, ctx: StageContext) -> StageResult:
            raise PermanentStageError("brief has unsourced claims")

    ep = _episode(scope)
    Worker(Lane.LLM, Workflow([Invalid(), Script(), Voice()]), scope,
           Settings(content_dir=tmp_path), worker_id="t").run_once()
    with scope() as s:
        job = s.scalars(select(ProductionJob).where(ProductionJob.episode_id == ep,
                                                    ProductionJob.stage == "research")).one()
        assert job.status is JobStatus.FAILED_PERMANENT and job.attempt == 1
        assert "unsourced" in (job.error_message or "")


def test_retry_stage_invalidates_downstream_only(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ep = _episode(scope)
    _worker(scope, Lane.LLM, tmp_path).run_until_idle()
    _worker(scope, Lane.MEDIA, tmp_path).run_until_idle()
    with scope() as s:
        queue.retry_stage(s, ep, "script", wf())
    st = _status(scope, ep)
    assert st == {"research": JobStatus.SUCCEEDED, "script": JobStatus.QUEUED,
                  "voice": JobStatus.PENDING}
    CALLS.clear()
    _worker(scope, Lane.LLM, tmp_path).run_until_idle()
    assert CALLS == ["script"]  # research reused, not re-run


def test_cancel_episode(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ep = _episode(scope)
    with scope() as s:
        assert queue.cancel_episode(s, ep) == 3
        assert s.get(Episode, ep).status is EpisodeStatus.CANCELLED
    assert _worker(scope, Lane.LLM, tmp_path).run_once() is None


def test_stale_lease_is_recovered(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _episode(scope)
    with scope() as s:
        job = queue.claim_next(s, Lane.LLM, "crashed-worker")
        assert job is not None
        job.locked_at = utcnow() - timedelta(hours=2)
    outcome = _worker(scope, Lane.LLM, tmp_path).run_once()
    assert outcome is not None and outcome.stage == "research"
    assert outcome.status is JobStatus.SUCCEEDED


def test_sync_adds_new_stages_to_existing_episode(scope, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ep = _episode(scope)
    _worker(scope, Lane.LLM, tmp_path).run_until_idle()
    _worker(scope, Lane.MEDIA, tmp_path).run_until_idle()

    class Subtitles(Stage):
        name, lane, depends_on = "subtitles", Lane.MEDIA, ("voice",)

        def run(self, ctx: StageContext) -> StageResult:
            return StageResult({"srt": "en.srt"})

    class Render(Stage):
        name, lane, depends_on = "render", Lane.RENDER, ("subtitles",)

    grown = Workflow([Research(), Script(), Voice(), Subtitles(), Render()])
    with scope() as s:
        added = {j.stage: j.status for j in queue.sync_episode_jobs(s, ep, grown)}
        assert added == {"subtitles": JobStatus.QUEUED, "render": JobStatus.PENDING}
        assert s.get(Episode, ep).status is EpisodeStatus.IN_PRODUCTION
        assert queue.sync_episode_jobs(s, ep, grown) == []  # idempotent


def test_backoff_is_capped() -> None:
    import random

    assert queue.backoff_delay(1, random.Random(0)) >= timedelta(seconds=60)
    assert queue.backoff_delay(20, random.Random(0)) <= timedelta(minutes=33)
