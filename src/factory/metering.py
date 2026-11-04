"""Usage metering: one `model_usage` row per external or subscription-metered call.

On the free-first stack (`claude -p` on a subscription) `cost_usd` holds the
CLI-reported *equivalent API cost*. It is not billed, but it shows which stages
consume the most subscription capacity and what a paid adapter would cost.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from factory.db.base import utcnow
from factory.db.models import ModelUsage

SessionFactory = Callable[[], AbstractContextManager[Session]]


class UsageRecorder:
    def __init__(self, session_scope: SessionFactory, episode_id: uuid.UUID | None = None):
        self.session_scope = session_scope
        self.episode_id = episode_id

    def record(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        units: dict[str, Any] | None = None,
        cost_usd: float | Decimal = 0,
        request_hash: str | None = None,
        latency_ms: int | None = None,
        execution_id: uuid.UUID | None = None,
    ) -> None:
        with self.session_scope() as s:
            s.add(
                ModelUsage(
                    execution_id=execution_id,
                    episode_id=self.episode_id,
                    provider=provider,
                    model=model,
                    operation=operation,
                    units=units or {},
                    cost_usd=Decimal(str(cost_usd)),
                    request_hash=request_hash,
                    latency_ms=latency_ms,
                )
            )


def calls_since(session: Session, provider: str, since: datetime) -> int:
    return session.scalar(
        select(func.count(ModelUsage.id)).where(
            ModelUsage.provider == provider, ModelUsage.created_at >= since
        )
    ) or 0


def calls_last_24h(session: Session, provider: str) -> int:
    return calls_since(session, provider, utcnow() - timedelta(hours=24))
