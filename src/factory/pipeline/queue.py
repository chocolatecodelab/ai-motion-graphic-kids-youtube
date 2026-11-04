r"""Postgres-backed job queue and state machine (docs/WORKFLOW_SPECIFICATION.md).

pending --deps met--> queued --claimed--> running --> succeeded
                                            |      \-> awaiting_approval --approve--> succeeded
                                            |-> failed_retryable --backoff--> (claimable again)
                                            |-> failed_permanent
                                            \-> cancelled

All functions take a Session and leave commit to the caller, so each state
change happens in one short transaction. Claiming uses FOR UPDATE SKIP LOCKED
on Postgres, so several workers can share a lane safely.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from factory.db.base import utcnow
from factory.db.models import Episode, EpisodeStatus, JobStatus, Lane, ProductionJob
from factory.pipeline.stage import Workflow

CLAIMABLE = (JobStatus.QUEUED, JobStatus.FAILED_RETRYABLE)
TERMINAL_OK = (JobStatus.SUCCEEDED,)
ACTIVE = (
    JobStatus.PENDING,
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.AWAITING_APPROVAL,
    JobStatus.FAILED_RETRYABLE,
)


def backoff_delay(attempt: int, rng: random.Random | None = None) -> timedelta:
    """min(2^attempt * 30 s, 30 min) + up to 10% jitter."""
    base = min((2**attempt) * 30, 30 * 60)
    jitter = (rng or random).uniform(0, base * 0.1)
    return timedelta(seconds=base + jitter)


def enqueue_episode(
    session: Session, episode_id: uuid.UUID, workflow: Workflow
) -> list[ProductionJob]:
    """Create one job per stage. Stages without dependencies start queued."""
    existing = session.scalars(
        select(ProductionJob).where(
            ProductionJob.episode_id == episode_id, ProductionJob.status.in_(ACTIVE)
        )
    ).first()
    if existing is not None:
        raise ValueError(f"episode {episode_id} already has active jobs")
    jobs = []
    for name in workflow.order:
        stage = workflow.stages[name]
        job = ProductionJob(
            episode_id=episode_id,
            stage=name,
            stage_version=stage.version,
            lane=stage.lane,
            status=JobStatus.QUEUED if not stage.depends_on else JobStatus.PENDING,
            max_attempts=stage.max_attempts,
            run_after=utcnow(),
        )
        session.add(job)
        jobs.append(job)
    episode = session.get(Episode, episode_id)
    if episode is not None and episode.status == EpisodeStatus.PLANNED:
        episode.status = EpisodeStatus.IN_PRODUCTION
    session.flush()
    return jobs


def sync_episode_jobs(
    session: Session, episode_id: uuid.UUID, workflow: Workflow
) -> list[ProductionJob]:
    """Add jobs for stages the workflow gained after the episode was created.

    New jobs start queued if all their dependencies already succeeded, else pending.
    """
    existing = {
        j.stage for j in session.scalars(
            select(ProductionJob).where(ProductionJob.episode_id == episode_id))
    }
    added: list[ProductionJob] = []
    for name in workflow.order:
        if name in existing:
            continue
        stage = workflow.stages[name]
        deps_done = all(
            (j := _job(session, episode_id, d)) is not None and j.status == JobStatus.SUCCEEDED
            for d in stage.depends_on
        )
        job = ProductionJob(
            episode_id=episode_id, stage=name, stage_version=stage.version, lane=stage.lane,
            status=JobStatus.QUEUED if deps_done else JobStatus.PENDING,
            max_attempts=stage.max_attempts, run_after=utcnow(),
        )
        session.add(job)
        session.flush()
        added.append(job)
    if added:
        episode = session.get(Episode, episode_id)
        if episode is not None and episode.status == EpisodeStatus.READY:
            episode.status = EpisodeStatus.IN_PRODUCTION
        session.flush()
    return added


def claim_next(
    session: Session, lane: Lane, worker_id: str, now: datetime | None = None
) -> ProductionJob | None:
    now = now or utcnow()
    job = session.scalars(
        select(ProductionJob)
        .where(
            ProductionJob.lane == lane,
            ProductionJob.status.in_(CLAIMABLE),
            ProductionJob.run_after <= now,
        )
        .order_by(ProductionJob.run_after, ProductionJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.attempt += 1
    job.locked_by = worker_id
    job.locked_at = now
    job.started_at = now
    job.error_class = None
    job.error_message = None
    session.flush()
    return job


def find_cached(session: Session, stage: str, input_hash: str) -> ProductionJob | None:
    """A previous successful run of the same stage with identical inputs."""
    return session.scalars(
        select(ProductionJob)
        .where(
            ProductionJob.stage == stage,
            ProductionJob.input_hash == input_hash,
            ProductionJob.status == JobStatus.SUCCEEDED,
        )
        .order_by(ProductionJob.finished_at.desc())
        .limit(1)
    ).first()


def _promote_dependents(session: Session, job: ProductionJob, workflow: Workflow) -> None:
    for name in workflow.dependents(job.stage):
        dep_job = _job(session, job.episode_id, name)
        if dep_job is None or dep_job.status != JobStatus.PENDING:
            continue
        needs = workflow.stages[name].depends_on
        done = {
            j.stage
            for j in session.scalars(
                select(ProductionJob).where(
                    ProductionJob.episode_id == job.episode_id,
                    ProductionJob.stage.in_(needs),
                    ProductionJob.status == JobStatus.SUCCEEDED,
                )
            )
        }
        if set(needs) <= done:
            dep_job.status = JobStatus.QUEUED
            dep_job.run_after = utcnow()


def _maybe_finish_episode(session: Session, episode_id: uuid.UUID) -> None:
    statuses = set(
        session.scalars(select(ProductionJob.status).where(ProductionJob.episode_id == episode_id))
    )
    episode = session.get(Episode, episode_id)
    if episode is None:
        return
    if statuses == {JobStatus.SUCCEEDED}:
        episode.status = EpisodeStatus.READY
    elif JobStatus.AWAITING_APPROVAL in statuses:
        episode.status = EpisodeStatus.AWAITING_APPROVAL
    elif episode.status == EpisodeStatus.AWAITING_APPROVAL:
        episode.status = EpisodeStatus.IN_PRODUCTION


def complete(
    session: Session,
    job: ProductionJob,
    workflow: Workflow,
    output_refs: dict,
    input_hash: str | None,
    awaiting_approval: bool = False,
) -> None:
    job.output_refs = output_refs
    job.input_hash = input_hash
    job.finished_at = utcnow()
    job.locked_by = None
    job.locked_at = None
    if awaiting_approval:
        job.status = JobStatus.AWAITING_APPROVAL
    else:
        job.status = JobStatus.SUCCEEDED
        _promote_dependents(session, job, workflow)
    session.flush()
    _maybe_finish_episode(session, job.episode_id)
    session.flush()


def fail(
    session: Session, job: ProductionJob, exc: BaseException, *, retryable: bool
) -> None:
    job.error_class = type(exc).__name__
    job.error_message = str(exc)[:4000]
    job.finished_at = utcnow()
    job.locked_by = None
    job.locked_at = None
    if retryable and job.attempt < job.max_attempts:
        job.status = JobStatus.FAILED_RETRYABLE
        job.run_after = utcnow() + backoff_delay(job.attempt)
    else:
        job.status = JobStatus.FAILED_PERMANENT
        episode = session.get(Episode, job.episode_id)
        if episode is not None:
            episode.status = EpisodeStatus.FAILED
    session.flush()


def approve(session: Session, episode_id: uuid.UUID, stage: str, workflow: Workflow) -> None:
    job = _job(session, episode_id, stage)
    if job is None or job.status != JobStatus.AWAITING_APPROVAL:
        raise ValueError(f"stage {stage!r} of {episode_id} is not awaiting approval")
    job.status = JobStatus.SUCCEEDED
    _promote_dependents(session, job, workflow)
    session.flush()
    _maybe_finish_episode(session, episode_id)
    session.flush()


def retry_stage(session: Session, episode_id: uuid.UUID, stage: str, workflow: Workflow) -> None:
    """Re-run one stage; everything downstream goes back to pending (invalidated).

    Succeeded upstream outputs are reused untouched.
    """
    job = _job(session, episode_id, stage)
    if job is None:
        raise ValueError(f"no job for stage {stage!r} in episode {episode_id}")
    if job.status == JobStatus.RUNNING:
        raise ValueError(f"stage {stage!r} is running; cancel it first")
    job.status = JobStatus.QUEUED
    job.attempt = 0
    job.run_after = utcnow()
    job.error_class = job.error_message = None
    job.input_hash = None  # force a fresh run, not a cache hit of the same inputs
    for name in workflow.downstream(stage):
        down = _job(session, episode_id, name)
        if down is not None and down.status != JobStatus.RUNNING:
            down.status = JobStatus.PENDING
            down.attempt = 0
            down.error_class = down.error_message = None
    episode = session.get(Episode, episode_id)
    if episode is not None:
        episode.status = EpisodeStatus.IN_PRODUCTION
    session.flush()


def cancel_episode(session: Session, episode_id: uuid.UUID) -> int:
    result = session.execute(
        update(ProductionJob)
        .where(ProductionJob.episode_id == episode_id, ProductionJob.status.in_(ACTIVE))
        .values(status=JobStatus.CANCELLED, locked_by=None, locked_at=None)
    )
    episode = session.get(Episode, episode_id)
    if episode is not None:
        episode.status = EpisodeStatus.CANCELLED
        episode.cancelled_at = utcnow()
    session.flush()
    return result.rowcount or 0


def recover_stale(session: Session, lane: Lane, timeout: timedelta) -> int:
    """Jobs left `running` by a crashed worker become claimable again."""
    cutoff = utcnow() - timeout
    stale = session.scalars(
        select(ProductionJob).where(
            ProductionJob.lane == lane,
            ProductionJob.status == JobStatus.RUNNING,
            ProductionJob.locked_at < cutoff,
        )
    ).all()
    for job in stale:
        job.status = JobStatus.FAILED_RETRYABLE
        job.error_class = "StaleLease"
        job.error_message = f"worker {job.locked_by} did not finish within {timeout}"
        job.locked_by = None
        job.locked_at = None
        job.run_after = utcnow()
    session.flush()
    return len(stale)


def _job(session: Session, episode_id: uuid.UUID, stage: str) -> ProductionJob | None:
    return session.scalars(
        select(ProductionJob)
        .where(ProductionJob.episode_id == episode_id, ProductionJob.stage == stage)
        .order_by(ProductionJob.created_at.desc())
        .limit(1)
    ).first()


def upstream_outputs(
    session: Session, episode_id: uuid.UUID, stages: tuple[str, ...]
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in stages:
        job = _job(session, episode_id, name)
        if job is None or job.status != JobStatus.SUCCEEDED:
            raise ValueError(f"upstream stage {name!r} has not succeeded")
        out[name] = dict(job.output_refs or {})
    return out
