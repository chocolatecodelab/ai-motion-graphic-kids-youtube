"""Storyboard v1: the machine-readable contract between Python and Remotion.

Component names and rig IDs are validated against config/catalogue/*.yaml by
code (agents/storyboard.py), so the JSON Schema stays generic and small.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from factory.schemas.script import Beat

CameraMove = Literal["static", "push_in", "pull_out", "pan", "parallax", "orbit"]
Easing = Literal["linear", "ease_in", "ease_out", "ease_in_out", "spring"]
TransitionType = Literal["compass_portal", "wipe", "cut", "zoom_through", "fade"]


class CharacterAction(BaseModel):
    character: Literal["kai", "needle"]
    pose: str = Field(description="Rig pose ID from the rig contract")
    expression: str = Field(description="Rig expression ID from the rig contract")
    action: str | None = Field(default=None, description="Optional rig action ID")
    position: Literal["left", "center", "right", "offscreen"] = "left"


class Background(BaseModel):
    library_id: str | None = Field(default=None, description="Reuse an existing library scene")
    asset_request: str | None = Field(
        default=None, max_length=300,
        description="Description of a new background (vector style, no text)",
    )
    parallax_layers: int = Field(default=3, ge=1, le=5)


class Camera(BaseModel):
    move: CameraMove = "static"
    zoom_from: float = Field(default=1.0, ge=0.5, le=3.0)
    zoom_to: float = Field(default=1.0, ge=0.5, le=3.0)
    easing: Easing = "ease_in_out"


class MotionGraphic(BaseModel):
    component: str = Field(description="Component name from the catalogue")
    props: dict[str, Any] = Field(default_factory=dict)
    at_line: str | None = Field(default=None, description="Line ID that triggers it")
    illustrative: bool = Field(
        default=False,
        description="True if numbers in props are only relative shapes for a qualitative idea. "
                    "The renderer then shows no numbers, axes or units.",
    )
    claim_ids: list[str] = Field(
        default_factory=list,
        description="Verified claims that state the numbers shown (required unless illustrative)",
    )


class SoundEffect(BaseModel):
    id: str = Field(max_length=60, description="Descriptive SFX id, e.g. whoosh_soft")
    at_line: str | None = None


class Transition(BaseModel):
    type: TransitionType = "cut"
    duration_s: float = Field(default=0.5, ge=0, le=3)


class StoryboardScene(BaseModel):
    scene_id: str = Field(pattern=r"^S\d{2}$")
    beat: Beat
    objective: str = Field(max_length=200)
    duration_s: float = Field(gt=0, le=120)
    line_ids: list[str] = Field(description="Script line IDs spoken in this scene, in order")
    characters: list[CharacterAction] = Field(min_length=1, max_length=2)
    background: Background
    camera: Camera = Camera()
    motion_graphics: list[MotionGraphic] = Field(default_factory=list)
    sfx: list[SoundEffect] = Field(default_factory=list)
    transition_out: Transition = Transition()
    educational_purpose: str = Field(max_length=200)


class StoryboardDraft(BaseModel):
    """LLM output."""

    scenes: list[StoryboardScene] = Field(min_length=6, max_length=24)


class Storyboard(BaseModel):
    schema_version: Literal["storyboard.v1"] = "storyboard.v1"
    episode_slug: str
    script_version: int
    fps: int = 30
    width: int = 1920
    height: int = 1080
    scenes: list[StoryboardScene]
    total_duration_s: float
    catalogue_version: str
    rig_version: str
