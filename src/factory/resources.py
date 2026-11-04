"""Versioned prompt templates, shared context and catalogues (rig + components).

Their content hashes are part of each stage's input hash, so editing a prompt or
the catalogue re-runs only the stages that use it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts"
CATALOGUE = ROOT / "config" / "catalogue"
SHARED_CONTEXT = ("brand_story.md", "kids_safety.md", "characters_v0.md")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=64)
def prompt(name: str) -> str:
    """e.g. prompt('script/v1')"""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def shared_context() -> str:
    parts = [(PROMPTS / "shared" / f).read_text(encoding="utf-8") for f in SHARED_CONTEXT]
    return "\n\n---\n\n".join(parts)


def render(template: str, **values: Any) -> str:
    return template.format_map({k: str(v) for k, v in values.items()})


@dataclass(frozen=True)
class Rig:
    version: str
    characters: dict[str, dict[str, Any]]

    def ids(self, character: str, kind: str) -> set[str]:
        return set(self.characters.get(character, {}).get(kind, []))

    def describe(self) -> str:
        out = []
        for name, c in self.characters.items():
            out.append(f"- {name}: poses {c['poses']}; expressions {c['expressions']}; "
                       f"actions {c['actions']}")
        return "\n".join(out)


@dataclass(frozen=True)
class Components:
    version: str
    items: dict[str, dict[str, Any]]

    def describe(self) -> str:
        return "\n".join(
            f"- {name}: {c['purpose']} (props: {c['props']})" for name, c in self.items.items()
        )


@lru_cache(maxsize=1)
def rig() -> Rig:
    data = yaml.safe_load((CATALOGUE / "rig_v0.yaml").read_text(encoding="utf-8"))
    return Rig(data["version"], data["characters"])


@lru_cache(maxsize=1)
def components() -> Components:
    data = yaml.safe_load((CATALOGUE / "components.yaml").read_text(encoding="utf-8"))
    return Components(data["version"], data["components"])


def resource_hash(*names: str) -> str:
    """Hash of prompt templates + shared context + catalogues used by a stage."""
    blob = "\n".join(prompt(n) for n in names) + shared_context()
    blob += (CATALOGUE / "rig_v0.yaml").read_text(encoding="utf-8")
    blob += (CATALOGUE / "components.yaml").read_text(encoding="utf-8")
    return sha256_text(blob)
