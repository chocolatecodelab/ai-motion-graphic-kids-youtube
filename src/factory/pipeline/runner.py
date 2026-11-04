"""Worker loop: claim a job, run its stage outside any DB transaction, record the outcome.

Three short transactions per job (claim -> [run] -> complete/fail), so a long LLM
call or render never holds a database lock.
"""

from __future__ import annotations

import os
import socket
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from factory.config import Settings
from factory.db.models import Episode, JobStatus, Lane, ProductionJob
from factory.log import get_logger
from factory.metering import UsageRecorder
from factory.pipeline import queue
from factory.pipeline.stage import (
    PermanentStageError,
    RetryableStageError,
    RevisionRequested,
    StageContext,
    StageResult,
    Workflow,
)

log = get_logger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class RunOutcome:
    job_id: uuid.UUID
    stage: str
    status: JobStatus
    cache_hit: bool = False


def default_worker_id(lane: Lane) -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{lane.value}"


class Worker:
    def __init__(
        self,
        lane: Lane,
        workflow: Workflow,
        session_scope: SessionFactory,
        settings: Settings,
        worker_id: str | None = None,
        lease_timeout: timedelta = timedelta(minutes=60),
    ):
        self.lane = lane
        self.workflow = workflow
        self.session_scope = session_scope
        self.settings = settings
        self.worker_id = worker_id or default_worker_id(lane)
        self.lease_timeout = lease_timeout

    def run_once(self) -> RunOutcome | None:
        """Process at most one job. Returns None when nothing is claimable."""
        with self.session_scope() as s:
            queue.recover_stale(s, self.lane, self.lease_timeout)
            job = queue.claim_next(s, self.lane, self.worker_id)
            if job is None:
                return None
            stage = self.workflow.stages.get(job.stage)
            if stage is None:
                queue.fail(s, job, LookupError(f"stage {job.stage!r} not in workflow"),
                           retryable=False)
                return RunOutcome(job.id, job.stage, JobStatus.FAILED_PERMANENT)
            episode = s.get(Episode, job.episode_id)
            assert episode is not None
            upstream = queue.upstream_outputs(s, job.episode_id, stage.depends_on)
            ctx = self._context(job, episode, upstream)
            job_id, stage_name = job.id, job.stage

        bound = log.bind(job_id=str(job_id), stage=stage_name, episode_id=str(ctx.episode_id))
        input_hash = stage.input_hash(ctx)

        with self.session_scope() as s:
            cached = queue.find_cached(s, stage_name, input_hash)
            if cached is not None and cached.id != job_id:
                job = s.get(ProductionJob, job_id)
                assert job is not None
                queue.complete(s, job, self.workflow, dict(cached.output_refs), input_hash)
                bound.info("stage cache hit", source_job=str(cached.id))
                return RunOutcome(job_id, stage_name, job.status, cache_hit=True)

        started = time.perf_counter()
        bound.info("stage started", attempt=ctx.attempt)
        try:
            result = stage.run(ctx)
            if not isinstance(result, StageResult):
                raise PermanentStageError(f"stage returned {type(result).__name__}")
        except RevisionRequested as exc:
            return self._request_revision(job_id, stage_name, exc, started)
        except PermanentStageError as exc:
            return self._fail(job_id, stage_name, exc, retryable=False, started=started)
        except RetryableStageError as exc:
            return self._fail(job_id, stage_name, exc, retryable=True, started=started)
        except Exception as exc:  # noqa: BLE001 - unknown errors: retry, but bounded
            return self._fail(job_id, stage_name, exc, retryable=True, started=started)

        awaiting = stage.requires_approval(self.settings.publication_mode)
        with self.session_scope() as s:
            job = s.get(ProductionJob, job_id)
            assert job is not None
            if job.status == JobStatus.CANCELLED:
                bound.info("stage finished after cancellation; result discarded")
                return RunOutcome(job_id, stage_name, JobStatus.CANCELLED)
            queue.complete(s, job, self.workflow, result.output_refs, input_hash,
                           awaiting_approval=awaiting)
            status = job.status
        bound.info("stage finished", status=status.value,
                   duration_ms=int((time.perf_counter() - started) * 1000))
        return RunOutcome(job_id, stage_name, status)

    def run_until_idle(self, max_jobs: int = 1000) -> list[RunOutcome]:
        outcomes = []
        for _ in range(max_jobs):
            outcome = self.run_once()
            if outcome is None:
                break
            outcomes.append(outcome)
        return outcomes

    def _context(self, job: ProductionJob, episode: Episode, upstream: dict) -> StageContext:
        prefix = episode.storage_prefix or f"episodes/{episode.slug}"
        workdir = Path(self.settings.content_dir) / prefix / job.stage
        recorder = UsageRecorder(self.session_scope, episode_id=episode.id)
        return StageContext(
            episode_id=episode.id,
            job_id=job.id,
            stage=job.stage,
            attempt=job.attempt,
            settings=self.settings,
            workdir=workdir,
            upstream=upstream,
            record_usage=recorder.record,
        )

    def _request_revision(
        self, job_id: uuid.UUID, stage_name: str, exc: RevisionRequested, started: float
    ) -> RunOutcome:
        if exc.target not in self.workflow.stages or stage_name not in self.workflow.downstream(
            exc.target
        ):
            return self._fail(job_id, stage_name, PermanentStageError(
                f"invalid revision target {exc.target!r}: {exc}"), retryable=False,
                started=started)
        with self.session_scope() as s:
            job = s.get(ProductionJob, job_id)
            assert job is not None
            if job.status == JobStatus.CANCELLED:
                return RunOutcome(job_id, stage_name, JobStatus.CANCELLED)
            job.error_class = "RevisionRequested"
            job.error_message = str(exc)[:4000]
            # Release this (running) job so retry_stage can reset it to pending with the rest.
            job.status = JobStatus.PENDING
            job.locked_by = None
            job.locked_at = None
            queue.retry_stage(s, job.episode_id, exc.target, self.workflow)
            status = job.status  # reset to pending by retry_stage (downstream of target)
        log.info("revision requested", job_id=str(job_id), stage=stage_name,
                 target=exc.target, reason=str(exc)[:300],
                 duration_ms=int((time.perf_counter() - started) * 1000))
        return RunOutcome(job_id, stage_name, status)

    def _fail(
        self, job_id: uuid.UUID, stage_name: str, exc: BaseException, *, retryable: bool,
        started: float,
    ) -> RunOutcome:
        with self.session_scope() as s:
            job = s.get(ProductionJob, job_id)
            assert job is not None
            if job.status == JobStatus.CANCELLED:
                return RunOutcome(job_id, stage_name, JobStatus.CANCELLED)
            queue.fail(s, job, exc, retryable=retryable)
            status = job.status
        log.warning("stage failed", job_id=str(job_id), stage=stage_name,
                    status=status.value, error_class=type(exc).__name__, error=str(exc)[:500],
                    duration_ms=int((time.perf_counter() - started) * 1000))
        return RunOutcome(job_id, stage_name, status)
