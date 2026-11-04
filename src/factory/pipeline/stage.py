"""Stage contract: every pipeline step (agent) implements `Stage`.

A stage is a pure function of its saved inputs: upstream outputs + config.
That makes it independently retryable and cacheable by input hash
(docs/WORKFLOW_SPECIFICATION.md).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from factory.config import PublicationMode, Settings
from factory.db.models import Lane


class StageError(Exception):
    """Base class for stage failures."""


class RetryableStageError(StageError):
    """Transient failure (timeout, rate limit, 5xx). Retried with backoff."""


class PermanentStageError(StageError):
    """Validation/policy failure or bad input. Not retried; needs a human or upstream fix."""


class RevisionRequested(StageError):
    """A reviewing stage rejected an upstream artifact with actionable feedback.

    The runner re-queues `target` (which reads the feedback the reviewer saved) and
    resets everything downstream of it, including the reviewer.
    """

    def __init__(self, target: str, message: str):
        super().__init__(message)
        self.target = target


@dataclass(frozen=True)
class StageContext:
    episode_id: uuid.UUID
    job_id: uuid.UUID
    stage: str
    attempt: int
    settings: Settings
    workdir: Path
    upstream: Mapping[str, Mapping[str, Any]]  # stage name -> output_refs
    record_usage: Callable[..., None] = field(default=lambda **_: None)


@dataclass(frozen=True)
class StageResult:
    output_refs: dict[str, Any]


class Stage:
    """Subclass and set the class attributes, then implement `run`."""

    name: ClassVar[str]
    lane: ClassVar[Lane]
    version: ClassVar[str] = "1"
    depends_on: ClassVar[tuple[str, ...]] = ()
    max_attempts: ClassVar[int] = 3
    # Gate per publication mode; e.g. script approval in APPROVAL_REQUIRED.
    approval_modes: ClassVar[frozenset[PublicationMode]] = frozenset()

    def input_payload(self, ctx: StageContext) -> Mapping[str, Any]:
        """Everything that determines the output. Default: upstream outputs."""
        return {"upstream": {k: ctx.upstream[k] for k in sorted(ctx.upstream)}}

    def input_hash(self, ctx: StageContext) -> str:
        payload = {"stage": self.name, "version": self.version, "input": self.input_payload(ctx)}
        blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def requires_approval(self, mode: PublicationMode) -> bool:
        return mode in self.approval_modes

    def run(self, ctx: StageContext) -> StageResult:
        raise NotImplementedError


class Workflow:
    """A validated DAG of stages."""

    def __init__(self, stages: list[Stage]):
        self.stages: dict[str, Stage] = {}
        for s in stages:
            if s.name in self.stages:
                raise ValueError(f"duplicate stage {s.name!r}")
            self.stages[s.name] = s
        for s in stages:
            unknown = set(s.depends_on) - self.stages.keys()
            if unknown:
                raise ValueError(f"stage {s.name!r} depends on unknown {sorted(unknown)}")
        self.order = self._topological()

    def _topological(self) -> list[str]:
        order: list[str] = []
        state: dict[str, int] = {}  # 1 = visiting, 2 = done

        def visit(name: str) -> None:
            if state.get(name) == 2:
                return
            if state.get(name) == 1:
                raise ValueError(f"cycle detected at stage {name!r}")
            state[name] = 1
            for dep in self.stages[name].depends_on:
                visit(dep)
            state[name] = 2
            order.append(name)

        for name in self.stages:
            visit(name)
        return order

    def dependents(self, name: str) -> list[str]:
        return [s.name for s in self.stages.values() if name in s.depends_on]

    def downstream(self, name: str) -> list[str]:
        """All transitive dependents, in topological order."""
        seen: set[str] = set()
        stack = self.dependents(name)
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(self.dependents(n))
        return [n for n in self.order if n in seen]
