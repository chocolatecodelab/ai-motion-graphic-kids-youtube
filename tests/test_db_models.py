"""Schema invariants from docs/DATABASE_SCHEMA.md, checked on SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from factory.db.models import (
    Channel,
    ContentTopic,
    Episode,
    EpisodeStatus,
    JobStatus,
    Lane,
    Pillar,
    ProductionJob,
    Project,
)


def _channel_project(db: Session) -> tuple[Channel, Project]:
    ch = Channel(name="Explore Wonder Discover")
    pr = Project(channel=ch, name="Main Quest")
    db.add_all([ch, pr])
    db.flush()
    return ch, pr


def _topic(db: Session, ch: Channel, slug: str) -> ContentTopic:
    t = ContentTopic(
        channel_id=ch.id,
        slug=slug,
        title="Why is the sky blue?",
        central_question="Why is the sky blue?",
        pillar=Pillar.SCIENCE_SPACE,
    )
    db.add(t)
    db.flush()
    return t


def test_channel_defaults_are_child_safe(db: Session) -> None:
    ch, _ = _channel_project(db)
    assert ch.made_for_kids is True
    assert ch.publication_mode.value == "APPROVAL_REQUIRED"
    assert ch.full_automation_enabled_by is None


def test_duplicate_topic_slug_rejected(db: Session) -> None:
    ch, _ = _channel_project(db)
    _topic(db, ch, "why-is-the-sky-blue")
    with pytest.raises(IntegrityError):
        _topic(db, ch, "why-is-the-sky-blue")


def test_topic_used_by_at_most_one_episode(db: Session) -> None:
    ch, pr = _channel_project(db)
    t = _topic(db, ch, "sky")
    db.add(Episode(project_id=pr.id, topic_id=t.id, number=1, slug="ep-1"))
    db.flush()
    db.add(Episode(project_id=pr.id, topic_id=t.id, number=2, slug="ep-2"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_live_episode_per_daily_slot(db: Session) -> None:
    _, pr = _channel_project(db)
    db.add(Episode(project_id=pr.id, number=1, slug="a", publish_slot_date="2026-11-10"))
    db.flush()
    db.add(Episode(project_id=pr.id, number=2, slug="b", publish_slot_date="2026-11-10"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_cancelled_episode_frees_its_slot(db: Session) -> None:
    _, pr = _channel_project(db)
    db.add(
        Episode(
            project_id=pr.id, number=1, slug="a", publish_slot_date="2026-11-10",
            status=EpisodeStatus.CANCELLED,
        )
    )
    db.add(Episode(project_id=pr.id, number=2, slug="b", publish_slot_date="2026-11-10"))
    db.flush()  # no error


def test_job_defaults_and_status_check(db: Session) -> None:
    _, pr = _channel_project(db)
    ep = Episode(project_id=pr.id, number=1, slug="a")
    db.add(ep)
    db.flush()
    job = ProductionJob(episode_id=ep.id, stage="script", lane=Lane.LLM)
    db.add(job)
    db.flush()
    assert job.status is JobStatus.PENDING
    assert job.attempt == 0 and job.max_attempts == 3
    assert job.run_after is not None


def test_unknown_enum_value_rejected(db: Session) -> None:
    _, pr = _channel_project(db)
    ep = Episode(project_id=pr.id, number=1, slug="a")
    db.add(ep)
    db.flush()
    db.add(ProductionJob(episode_id=ep.id, stage="script", lane="gpu"))  # type: ignore[arg-type]
    with pytest.raises((StatementError, LookupError)):
        db.flush()
