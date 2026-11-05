"""Operations used by the CLI (and later the dashboard): create episodes, approve, look up."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from factory.config import Settings
from factory.db.models import (
    Approval,
    ApprovalDecision,
    ApprovalGate,
    Channel,
    ContentTopic,
    Episode,
    JobStatus,
    ProductionJob,
    Project,
    TopicStatus,
)
from factory.pipeline import Workflow, queue
from factory.schemas.brief import TopicBrief

CHANNEL_NAME = "Explore. Wonder. Discover."
GATE_FOR_STAGE = {"script_validate": ApprovalGate.SCRIPT, "storyboard": ApprovalGate.STORYBOARD}


def get_or_create_channel(s: Session, settings: Settings) -> Channel:
    ch = s.scalar(select(Channel).where(Channel.name == CHANNEL_NAME))
    if ch is None:
        ch = Channel(name=CHANNEL_NAME, timezone=settings.timezone,
                     publication_mode=settings.publication_mode)
        s.add(ch)
        s.flush()
    return ch


def get_or_create_project(s: Session, channel: Channel, name: str, brief: TopicBrief) -> Project:
    pr = s.scalar(select(Project).where(Project.channel_id == channel.id, Project.name == name))
    if pr is None:
        pr = Project(channel_id=channel.id, name=name,
                     target_duration_s_min=brief.duration.min_s,
                     target_duration_s_max=brief.duration.max_s)
        s.add(pr)
        s.flush()
    return pr


def create_episode_from_brief(
    s: Session, brief_path: Path, settings: Settings, workflow: Workflow,
    project_name: str = "Pilot",
) -> Episode:
    brief = TopicBrief.model_validate(yaml.safe_load(brief_path.read_text(encoding="utf-8")))
    channel = get_or_create_channel(s, settings)
    project = get_or_create_project(s, channel, project_name, brief)

    topic = s.scalar(select(ContentTopic).where(ContentTopic.channel_id == channel.id,
                                                ContentTopic.slug == brief.slug))
    if topic is not None:
        existing = s.scalar(select(Episode).where(Episode.topic_id == topic.id))
        if existing is not None:
            raise ValueError(f"topic {brief.slug!r} already has episode #{existing.number} "
                             f"({existing.slug}); use `factory retry` to re-run a stage")
    else:
        topic = ContentTopic(channel_id=channel.id, slug=brief.slug, title=brief.title,
                             central_question=brief.central_question, pillar=brief.pillar,
                             learning_objective="; ".join(brief.learning_objectives),
                             storytelling_angle=brief.storytelling_angle,
                             status=TopicStatus.SELECTED)
        s.add(topic)
        s.flush()

    number = (s.scalar(select(func.max(Episode.number)).where(Episode.project_id == project.id))
              or 0) + 1
    now = datetime.now(settings.tz)
    slug = f"ep-{number:04d}-{brief.slug}"
    episode = Episode(project_id=project.id, topic_id=topic.id, number=number, slug=slug,
                      storage_prefix=f"{now:%Y}/{now:%m}/{slug}")
    s.add(episode)
    s.flush()

    dest = Path(settings.content_dir) / episode.storage_prefix / "inputs" / "brief.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(brief_path, dest)
    topic.status = TopicStatus.USED
    queue.enqueue_episode(s, episode.id, workflow)
    return episode


def find_episode(s: Session, ref: str) -> Episode:
    conditions = [Episode.slug == ref]
    if ref.isdigit():
        conditions.append(Episode.number == int(ref))
    try:
        conditions.append(Episode.id == uuid.UUID(ref))
    except ValueError:
        pass
    found = s.scalars(select(Episode).where(or_(*conditions))).all()
    if not found:
        raise LookupError(f"no episode matches {ref!r}")
    if len(found) > 1:
        raise LookupError(f"{ref!r} matches {len(found)} episodes; use the slug")
    return found[0]


# Approval gate -> the stage that rewrites its input when the owner asks for changes.
REVISION_TARGET = {"script_validate": "script"}


def revise_stage(
    s: Session, episode: Episode, stage: str, workflow: Workflow, settings: Settings,
    decided_by: str, notes: str, include_review: bool = True,
) -> Path:
    """Owner sends a gated stage back with notes: the target stage rewrites using the notes
    (and the reviewer's findings), then the gate is reviewed again. Returns the feedback file."""
    target = REVISION_TARGET.get(stage)
    if target is None:
        raise ValueError(f"stage {stage!r} cannot be revised from its gate "
                         f"(supported: {sorted(REVISION_TARGET)})")
    job = s.scalar(select(ProductionJob).where(ProductionJob.episode_id == episode.id,
                                               ProductionJob.stage == stage))
    if job is None or job.status != JobStatus.AWAITING_APPROVAL:
        raise ValueError(f"stage {stage!r} of {episode.slug} is not awaiting approval")
    ep_dir = Path(settings.content_dir) / episode.storage_prefix
    text = f"# Owner revision request ({decided_by})\n\n{notes.strip()}\n"
    reviews = sorted((ep_dir / stage).glob("review.v*.md"),
                     key=lambda p: int(p.stem.rsplit(".v", 1)[1]))
    if include_review and reviews:
        text += ("\n## The reviewer's findings (apply the ones the owner asks for)\n\n"
                 + reviews[-1].read_text(encoding="utf-8"))
    fb_dir = ep_dir / "inputs" / "feedback"
    fb_dir.mkdir(parents=True, exist_ok=True)
    n = 1 + max((int(p.stem.rsplit(".v", 1)[1]) for p in fb_dir.glob(f"{target}.v*.md")
                 if p.stem.rsplit(".v", 1)[1].isdigit()), default=0)
    path = fb_dir / f"{target}.v{n}.md"
    path.write_text(text, encoding="utf-8")
    s.add(Approval(episode_id=episode.id, gate=GATE_FOR_STAGE.get(stage, ApprovalGate.FINAL),
                   decision=ApprovalDecision.REJECTED, decided_by=decided_by, notes=notes))
    queue.retry_stage(s, episode.id, target, workflow)
    s.flush()
    return path


def approve_stage(
    s: Session, episode: Episode, stage: str, workflow: Workflow, decided_by: str,
    notes: str | None = None,
) -> None:
    queue.approve(s, episode.id, stage, workflow)
    s.add(Approval(episode_id=episode.id, gate=GATE_FOR_STAGE.get(stage, ApprovalGate.FINAL),
                   decision=ApprovalDecision.APPROVED, decided_by=decided_by, notes=notes))
    s.flush()
