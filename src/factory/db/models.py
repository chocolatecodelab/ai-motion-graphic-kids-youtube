"""Core schema, migration 0001 (see docs/DATABASE_SCHEMA.md).

Included now: channels, projects, characters, character_versions, content_topics,
episodes, production_jobs (queue + state machine), agent_executions, model_usage,
visual_assets, audio_assets, asset_links, approvals, budgets, settings, system_logs.

Added by later migrations as their stages are built: research_sources,
research_reports, claims, scripts, storyboards, scenes, render_jobs, qa_reports,
thumbnails, youtube_videos, publishing_schedules, analytics_snapshots,
oauth_credentials.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from factory.config import PublicationMode
from factory.db.base import Base, IdTimestampMixin, JSONType, utcnow


def _enum(e: type[StrEnum], name: str) -> Enum:
    """VARCHAR + CHECK constraint: portable (Postgres/SQLite) and easy to extend."""
    return Enum(
        e,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda x: [m.value for m in x],
        validate_strings=True,
    )


# ---------------------------------------------------------------- enums


class CharacterRole(StrEnum):
    HERO = "hero"
    COMPANION = "companion"


class CharacterStatus(StrEnum):
    CONCEPT = "concept"
    APPROVED = "approved"
    RETIRED = "retired"


class RigType(StrEnum):
    VECTOR_PUPPET = "vector_puppet"
    POSE_LIBRARY_3D = "pose_library_3d"
    THREE_GLB = "three_glb"


class ProjectFormat(StrEnum):
    LONG = "long"
    SHORT = "short"


class Pillar(StrEnum):
    NATURE = "nature_living_world"
    HOW_THINGS_WORK = "how_things_work"
    SCIENCE_SPACE = "science_space"
    HISTORY = "history_civilization"
    MYSTERIES = "curious_mysteries"


class TopicStatus(StrEnum):
    CANDIDATE = "candidate"
    SELECTED = "selected"
    REJECTED = "rejected"
    USED = "used"


class EpisodeStatus(StrEnum):
    PLANNED = "planned"
    IN_PRODUCTION = "in_production"
    AWAITING_APPROVAL = "awaiting_approval"
    QA_FAILED = "qa_failed"
    READY = "ready"
    UPLOADED = "uploaded"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Lane(StrEnum):
    LLM = "llm"
    MEDIA = "media"
    RENDER = "render"
    PUBLISH = "publish"


class JobStatus(StrEnum):
    """Job state machine, docs/WORKFLOW_SPECIFICATION.md."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    CANCELLED = "cancelled"


class AssetScope(StrEnum):
    LIBRARY = "library"
    EPISODE = "episode"


class VisualKind(StrEnum):
    BACKGROUND = "background"
    PARALLAX_LAYER = "parallax_layer"
    PROP = "prop"
    DIAGRAM = "diagram"
    CHARACTER_POSE = "character_pose"
    THUMBNAIL = "thumbnail"
    CONCEPT = "concept"


class AudioKind(StrEnum):
    VO_LINE = "vo_line"
    VO_FULL = "vo_full"
    MUSIC_BED = "music_bed"
    SFX = "sfx"
    MIX = "mix"


class AssetQAStatus(StrEnum):
    PENDING = "pending"
    OK = "ok"
    REJECTED = "rejected"


class ApprovalGate(StrEnum):
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    FINAL = "final"
    PUBLISH = "publish"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class BudgetScope(StrEnum):
    DAILY = "daily"
    MONTHLY = "monthly"
    EPISODE = "episode"


# ---------------------------------------------------------------- channel / projects


class Channel(IdTimestampMixin, Base):
    __tablename__ = "channels"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    youtube_channel_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    default_language: Mapped[str] = mapped_column(String(16), default="en")
    made_for_kids: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Jakarta")
    publication_mode: Mapped[PublicationMode] = mapped_column(
        _enum(PublicationMode, "publication_mode"), default=PublicationMode.APPROVAL_REQUIRED
    )
    full_automation_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    full_automation_enabled_by: Mapped[str | None] = mapped_column(String(120))
    brand_tokens: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    projects: Mapped[list[Project]] = relationship(back_populates="channel")


class Project(IdTimestampMixin, Base):
    """A series/format within a channel (Main Quest, Compass Glitch, Shorts)."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("channel_id", "name"),)

    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    format: Mapped[ProjectFormat] = mapped_column(
        _enum(ProjectFormat, "project_format"), default=ProjectFormat.LONG
    )
    target_duration_s_min: Mapped[int] = mapped_column(Integer, default=300)
    target_duration_s_max: Mapped[int] = mapped_column(Integer, default=480)
    template_id: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    channel: Mapped[Channel] = relationship(back_populates="projects")
    episodes: Mapped[list[Episode]] = relationship(back_populates="project")


# ---------------------------------------------------------------- characters


class Character(IdTimestampMixin, Base):
    __tablename__ = "characters"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[CharacterRole] = mapped_column(_enum(CharacterRole, "character_role"))
    status: Mapped[CharacterStatus] = mapped_column(
        _enum(CharacterStatus, "character_status"), default=CharacterStatus.CONCEPT
    )

    versions: Mapped[list[CharacterVersion]] = relationship(back_populates="character")


class CharacterVersion(IdTimestampMixin, Base):
    __tablename__ = "character_versions"
    __table_args__ = (UniqueConstraint("character_id", "version"),)

    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    bible: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    rig_contract: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    rig_type: Mapped[RigType] = mapped_column(
        _enum(RigType, "rig_type"), default=RigType.VECTOR_PUPPET
    )
    reference_sheet_key: Mapped[str | None] = mapped_column(String(500))
    voice_provider: Mapped[str | None] = mapped_column(String(64))
    voice_id: Mapped[str | None] = mapped_column(String(128))
    voice_settings: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(120))

    character: Mapped[Character] = relationship(back_populates="versions")


# ---------------------------------------------------------------- planning


class ContentTopic(IdTimestampMixin, Base):
    __tablename__ = "content_topics"
    __table_args__ = (
        UniqueConstraint("channel_id", "slug"),  # duplicate-topic prevention
        Index("ix_content_topics_channel_status", "channel_id", "status"),
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    central_question: Mapped[str] = mapped_column(String(300))
    pillar: Mapped[Pillar] = mapped_column(_enum(Pillar, "pillar"))
    learning_objective: Mapped[str | None] = mapped_column(Text)
    target_age_min: Mapped[int] = mapped_column(SmallInteger, default=8)
    target_age_max: Mapped[int] = mapped_column(SmallInteger, default=12)
    storytelling_angle: Mapped[str | None] = mapped_column(Text)
    complexity: Mapped[int | None] = mapped_column(SmallInteger)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    status: Mapped[TopicStatus] = mapped_column(
        _enum(TopicStatus, "topic_status"), default=TopicStatus.CANDIDATE
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- episodes / queue


class Episode(IdTimestampMixin, Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        Index("ix_episodes_status", "status"),
        Index("ix_episodes_planned_publish_at", "planned_publish_at"),
        # Daily-slot uniqueness: one live episode per project per publish day.
        # publish_slot_date is the local date of planned_publish_at, set by the service layer
        # (portable alternative to an expression index on AT TIME ZONE).
        Index(
            "uq_episodes_daily_slot",
            "project_id",
            "publish_slot_date",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_topics.id"), unique=True
    )
    number: Mapped[int] = mapped_column(Integer)
    slug: Mapped[str] = mapped_column(String(200))
    character_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("character_versions.id")
    )
    workflow_version: Mapped[str] = mapped_column(String(32), default="1")
    status: Mapped[EpisodeStatus] = mapped_column(
        _enum(EpisodeStatus, "episode_status"), default=EpisodeStatus.PLANNED
    )
    planned_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_slot_date: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD, channel tz
    storage_prefix: Mapped[str | None] = mapped_column(String(500))
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="episodes")
    jobs: Mapped[list[ProductionJob]] = relationship(back_populates="episode")


class ProductionJob(IdTimestampMixin, Base):
    """One stage execution for an episode; also the work-queue row (claimed with SKIP LOCKED)."""

    __tablename__ = "production_jobs"
    __table_args__ = (
        Index("ix_production_jobs_claim", "status", "lane", "run_after"),
        Index("ix_production_jobs_episode_stage", "episode_id", "stage"),
        Index(
            "ix_production_jobs_cache",
            "stage",
            "input_hash",
            postgresql_where=text("status = 'succeeded'"),
            sqlite_where=text("status = 'succeeded'"),
        ),
    )

    episode_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(64))
    stage_version: Mapped[str] = mapped_column(String(32), default="1")
    lane: Mapped[Lane] = mapped_column(_enum(Lane, "lane"))
    status: Mapped[JobStatus] = mapped_column(
        _enum(JobStatus, "job_status"), default=JobStatus.PENDING
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    output_refs: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error_class: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    episode: Mapped[Episode] = relationship(back_populates="jobs")


class AgentExecution(IdTimestampMixin, Base):
    __tablename__ = "agent_executions"

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_jobs.id", ondelete="SET NULL")
    )
    agent: Mapped[str] = mapped_column(String(64))
    prompt_template_version: Mapped[str | None] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    input_ref: Mapped[str | None] = mapped_column(String(500))
    output_ref: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="succeeded")
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    error: Mapped[str | None] = mapped_column(Text)


class ModelUsage(IdTimestampMixin, Base):
    """Metering: one row per external (or subscription-metered) call."""

    __tablename__ = "model_usage"
    __table_args__ = (
        Index("ix_model_usage_created_at", "created_at"),
        Index("ix_model_usage_episode", "episode_id"),
        Index("ix_model_usage_provider_created", "provider", "created_at"),
    )

    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="SET NULL")
    )
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    operation: Mapped[str] = mapped_column(String(32))  # messages | web_search | tts | upload ...
    units: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)


# ---------------------------------------------------------------- assets (rights registry)


class VisualAsset(IdTimestampMixin, Base):
    __tablename__ = "visual_assets"
    __table_args__ = (
        UniqueConstraint("scope", "sha256"),
        Index("ix_visual_assets_scope_kind", "scope", "kind"),
    )

    scope: Mapped[AssetScope] = mapped_column(_enum(AssetScope, "visual_scope"))
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL")
    )
    kind: Mapped[VisualKind] = mapped_column(_enum(VisualKind, "visual_kind"))
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    mime: Mapped[str | None] = mapped_column(String(64))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    # NULL licence_ref blocks publication (rights gate).
    licence_ref: Mapped[str | None] = mapped_column(String(500))
    licence_terms_version: Mapped[str | None] = mapped_column(String(64))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    qa_status: Mapped[AssetQAStatus] = mapped_column(
        _enum(AssetQAStatus, "visual_qa_status"), default=AssetQAStatus.PENDING
    )
    created_by_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="SET NULL")
    )


class AudioAsset(IdTimestampMixin, Base):
    __tablename__ = "audio_assets"
    __table_args__ = (UniqueConstraint("scope", "sha256"),)

    scope: Mapped[AssetScope] = mapped_column(_enum(AssetScope, "audio_scope"))
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL")
    )
    kind: Mapped[AudioKind] = mapped_column(_enum(AudioKind, "audio_kind"))
    character_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("character_versions.id")
    )
    text: Mapped[str | None] = mapped_column(Text)
    timestamps_key: Mapped[str | None] = mapped_column(String(500))
    duration_s: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    lufs: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    licence_ref: Mapped[str | None] = mapped_column(String(500))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))


class AssetLink(IdTimestampMixin, Base):
    """Many-to-many reuse of library assets by episodes/scenes."""

    __tablename__ = "asset_links"
    __table_args__ = (
        UniqueConstraint("episode_id", "asset_type", "asset_id", "scene_key", "role"),
    )

    episode_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    asset_type: Mapped[str] = mapped_column(String(16))  # visual | audio
    scene_key: Mapped[str | None] = mapped_column(String(16))
    role: Mapped[str | None] = mapped_column(String(64))


# ---------------------------------------------------------------- governance / ops


class Approval(IdTimestampMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_episode_gate", "episode_id", "gate"),)

    episode_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    gate: Mapped[ApprovalGate] = mapped_column(_enum(ApprovalGate, "approval_gate"))
    decision: Mapped[ApprovalDecision] = mapped_column(
        _enum(ApprovalDecision, "approval_decision")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String(120))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class Budget(IdTimestampMixin, Base):
    __tablename__ = "budgets"

    scope: Mapped[BudgetScope] = mapped_column(_enum(BudgetScope, "budget_scope"), unique=True)
    soft_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    hard_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class Setting(IdTimestampMixin, Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), unique=True)
    value: Mapped[Any] = mapped_column(JSONType)


class SystemLog(IdTimestampMixin, Base):
    __tablename__ = "system_logs"
    __table_args__ = (Index("ix_system_logs_ts", "ts"),)

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    level: Mapped[str] = mapped_column(String(16))
    logger: Mapped[str] = mapped_column(String(120))
    episode_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
