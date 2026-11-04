"""Pydantic models for every stage artifact. `export_json_schemas()` writes them to schemas/."""

from __future__ import annotations

import json
from pathlib import Path

from factory.schemas.brief import TopicBrief
from factory.schemas.review import ScriptReview
from factory.schemas.script import Script
from factory.schemas.storyboard import Storyboard

ARTIFACT_MODELS = {
    "brief.v1": TopicBrief,
    "script.v1": Script,
    "review.v1": ScriptReview,
    "storyboard.v1": Storyboard,
}


def export_json_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in ARTIFACT_MODELS.items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written
