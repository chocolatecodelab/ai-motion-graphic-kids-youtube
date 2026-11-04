"""Versioned stage artifacts on disk (never in the DB). Paths in output_refs are
relative to the content directory so the store can move (local -> S3 later)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def next_version(workdir: Path, stem: str) -> int:
    existing = [int(m.group(1)) for p in workdir.glob(f"{stem}.v*.json")
                if (m := re.fullmatch(rf"{re.escape(stem)}\.v(\d+)\.json", p.name))]
    return max(existing, default=0) + 1


def write_model(
    content_dir: Path, workdir: Path, stem: str, model: BaseModel, version: int
) -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{stem}.v{version}.json"
    data = model.model_dump_json(indent=2).encode("utf-8")
    path.write_bytes(data)
    return {
        "path": path.resolve().relative_to(content_dir.resolve()).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "version": version,
    }


def write_text(content_dir: Path, path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.resolve().relative_to(content_dir.resolve()).as_posix()


def read_model(content_dir: Path, ref: dict[str, Any], model: type[M]) -> M:
    path = content_dir / ref["path"]
    data = path.read_bytes()
    if "sha256" in ref and hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError(f"artifact {ref['path']} changed on disk (sha256 mismatch)")
    return model.model_validate(json.loads(data))
