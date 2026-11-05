"""visual_plan + assets: set dressing per scene and the SVG props it needs (M2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PropDepth = Literal["far", "mid", "near", "front"]


class PropPlacement(BaseModel):
    ref: str = Field(description="builtin:<id> | asset:<library asset id> | new:<request_id>")
    x: float = Field(ge=-0.2, le=1.2, description="Horizontal position, 0..1 of the frame width")
    y: float = Field(ge=0.2, le=1.1,
                     description="Ground contact line, 0..1 of the frame height (ground ~0.93)")
    scale: float = Field(default=1.0, ge=0.3, le=2.5)
    depth: PropDepth = "near"
    flip: bool = False


class ScenePropPlan(BaseModel):
    scene_id: str = Field(pattern=r"^S\d{2}$")
    props: list[PropPlacement] = Field(default_factory=list, max_length=5)
    why: str = Field(default="", max_length=200, description="How the props tell this story")


class AssetRequest(BaseModel):
    request_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    kind: Literal["svg_prop"] = "svg_prop"
    name: str = Field(max_length=60, description="Short object name, e.g. 'brass telescope'")
    description: str = Field(max_length=300, description="What it looks like (no text/logos)")
    tags: list[str] = Field(default_factory=list, max_length=8)


class VisualPlanDraft(BaseModel):
    """LLM output."""

    scenes: list[ScenePropPlan]
    asset_requests: list[AssetRequest] = Field(default_factory=list, max_length=4)


class VisualPlan(BaseModel):
    schema_version: Literal["visual_plan.v1"] = "visual_plan.v1"
    episode_slug: str
    storyboard_version: int
    scenes: list[ScenePropPlan]
    asset_requests: list[AssetRequest]
    prop_catalogue_version: str


class SvgDraft(BaseModel):
    """LLM output for one asset."""

    svg: str = Field(description="One complete <svg> element, viewBox 0 0 400 400")


class AssetRecord(BaseModel):
    """One asset in the library index (provenance travels with the asset)."""

    asset_id: str
    name: str
    kind: Literal["svg_prop"] = "svg_prop"
    tags: list[str] = Field(default_factory=list)
    file: str  # relative to the library dir
    sha256: str
    created_at: str
    generator: str  # e.g. "claude_cli:claude-sonnet-5-5"
    prompt_sha256: str
    licence: str = "original: generated for this project, all rights owned"
    source_episode: str = ""


class AssetManifest(BaseModel):
    schema_version: Literal["assets.v1"] = "assets.v1"
    episode_slug: str
    resolved: dict[str, str] = Field(default_factory=dict,
                                     description="request_id -> library asset_id")
    generated: list[str] = Field(default_factory=list)
    reused: list[str] = Field(default_factory=list)
    attempts: dict[str, int] = Field(default_factory=dict)
