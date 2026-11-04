"""Character IDs shared by every schema (rig v2: Arka & Lipa).

Artifacts written before the Character Bible v2 use the rig v1 IDs `kai` / `needle`; they are
mapped on load so old scripts, storyboards and render plans keep validating and rendering.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BeforeValidator

LEGACY_IDS = {"kai": "arka", "needle": "lipa"}


def _upgrade(value: Any) -> Any:
    return LEGACY_IDS.get(value, value) if isinstance(value, str) else value


CharacterId = Annotated[Literal["arka", "lipa"], BeforeValidator(_upgrade)]
Focus = Annotated[
    Literal["arka", "lipa", "both", "graphic", "background"], BeforeValidator(_upgrade)
]

HERO: Literal["arka"] = "arka"
COMPANION: Literal["lipa"] = "lipa"
