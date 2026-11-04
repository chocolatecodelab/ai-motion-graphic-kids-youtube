"""Helpers shared by agent stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from factory import artifacts
from factory.pipeline import PermanentStageError, StageContext
from factory.schemas.brief import TopicBrief

M = TypeVar("M", bound=BaseModel)


def content_dir(ctx: StageContext) -> Path:
    return Path(ctx.settings.content_dir)


def episode_dir(ctx: StageContext) -> Path:
    return ctx.workdir.parent


def load_upstream(ctx: StageContext, stage: str, model: type[M]) -> M:
    ref = ctx.upstream.get(stage)
    if not ref or "path" not in ref:
        raise PermanentStageError(f"missing upstream artifact from {stage!r}")
    try:
        return artifacts.read_model(content_dir(ctx), ref, model)
    except FileNotFoundError as exc:
        raise PermanentStageError(f"upstream artifact missing on disk: {ref['path']}") from exc
    except (ValueError, ValidationError) as exc:
        raise PermanentStageError(f"upstream artifact from {stage!r} is invalid: {exc}") from exc


def claims_block(brief: TopicBrief) -> str:
    lines = []
    for c in brief.usable_claims():
        note = f" (note: {c.simplification_note})" if c.simplification_note else ""
        twist = " [TWIST]" if c.is_twist else ""
        lines.append(f"- {c.id}{twist}: {c.text}{note}")
    return "\n".join(lines)


def feedback_dir(ctx: StageContext) -> Path:
    return episode_dir(ctx) / "inputs" / "feedback"


def latest_feedback(ctx: StageContext, target: str) -> tuple[int, str]:
    """(version, text) of the newest reviewer feedback for `target`, or (0, "")."""
    d = feedback_dir(ctx)
    versions = sorted(
        (int(p.stem.rsplit(".v", 1)[1]), p) for p in d.glob(f"{target}.v*.md")
        if p.stem.rsplit(".v", 1)[-1].isdigit()
    ) if d.exists() else []
    if not versions:
        return 0, ""
    n, path = versions[-1]
    return n, path.read_text(encoding="utf-8")


def write_feedback(ctx: StageContext, target: str, text: str) -> int:
    n, _ = latest_feedback(ctx, target)
    d = feedback_dir(ctx)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{target}.v{n + 1}.md").write_text(text, encoding="utf-8")
    return n + 1


def save(ctx: StageContext, stem: str, model: BaseModel) -> dict[str, Any]:
    version = artifacts.next_version(ctx.workdir, stem)
    return artifacts.write_model(content_dir(ctx), ctx.workdir, stem, model, version)
