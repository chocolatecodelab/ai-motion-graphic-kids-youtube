"""Storyboard v2: the machine-readable contract between Python and Remotion.

v2 (owner direction, DECISIONS.md 2026-11-04) replaces the static left/right
character placement with **shots**. Each shot has a type, angle, camera move,
focus, and full character blocking: free position, depth, scale, facing,
entrances and exits, motion and a movement path timed to lines.

Component names and rig IDs are validated against config/catalogue/*.yaml by
code (agents/storyboard.py), so the JSON Schema stays generic and small.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from factory.schemas.characters import CharacterId, Focus
from factory.schemas.script import Beat

ShotType = Literal["extreme_wide", "wide", "medium", "close_up", "extreme_close_up",
                   "over_shoulder", "pov", "insert"]
Angle = Literal["eye_level", "low", "high", "birds_eye", "tilted"]
CameraMove = Literal["static", "zoom_in", "zoom_out", "dolly_in", "dolly_out", "pan_left",
                     "pan_right", "tilt_up", "tilt_down", "truck_left", "truck_right", "follow",
                     "whip_pan", "crane_up", "crane_down", "shake", "orbit"]
Depth = Literal["foreground", "midground", "background"]
Motion = Literal["none", "walk", "run", "fly", "float", "jump", "shrink", "grow", "spin",
                 "bounce", "zip"]
Entrance = Literal["none", "from_left", "from_right", "from_top", "from_bottom", "pop", "portal"]
TransitionType = Literal["compass_portal", "wipe", "cut", "zoom_through", "fade", "whip"]

# Shot types where the speaker may be off screen (voice heard over the image).
OFFSCREEN_OK_SHOTS = {"insert", "pov", "extreme_wide"}


class Waypoint(BaseModel):
    x: float = Field(ge=-0.3, le=1.3, description="0 = left edge, 1 = right edge")
    y: float = Field(ge=0.0, le=1.3, description="Feet/ground line; 0 = top, 1 = bottom")
    scale: float = Field(default=1.0, ge=0.1, le=4.0)
    at_line: str | None = Field(default=None, description="Reach this point by this line; "
                                                          "null = end of the shot")


class Blocking(BaseModel):
    character: CharacterId
    x: float = Field(ge=-0.3, le=1.3, description="Horizontal position, 0..1 of the frame")
    y: float = Field(ge=0.0, le=1.3, description="Ground line, 0..1 of the frame (1 = bottom)")
    scale: float = Field(default=1.0, ge=0.1, le=4.0, description="1 = medium-shot size")
    depth: Depth = "midground"
    facing: Literal["left", "right", "camera"] = "camera"
    pose: str = Field(description="Rig pose ID")
    expression: str = Field(description="Rig expression ID")
    action: str | None = Field(default=None, description="Optional rig action ID")
    enter: Entrance = "none"
    exit: Entrance = "none"
    motion: Motion = "none"
    path: list[Waypoint] = Field(default_factory=list, max_length=4)


class Shot(BaseModel):
    starts_at_line: str | None = Field(default=None, description="null = start of the scene")
    shot_type: ShotType
    angle: Angle = "eye_level"
    camera_move: CameraMove = "static"
    focus: Focus = "both"
    blocking: list[Blocking] = Field(default_factory=list, max_length=2)
    note: str = Field(default="", max_length=140, description="Director's intent")


# M2 SVG scene library (remotion/src/scene/bg/themes.tsx); keep in sync with types.ts Theme.
THEME_GUIDE: dict[str, str] = {
    "attic": "grandparent's attic, round window, shelves",
    "workbench": "attic workbench with lamp, gears and tools",
    "sunbeam": "inside a beam of light, rainbow ribbons, stars",
    "sky": "open sky, sun, clouds, green hills",
    "air": "among air molecules (N2/O2 pairs)",
    "sunset": "low sun, warm sky, purple hills, pines",
    "mars": "Martian landscape, rocks, blue-grey sun halo",
    "space": "stars, a ringed planet, Earth",
    "studio": "neutral paper backdrop with map contours",
    "forest": "pine forest, hills, falling leaves",
    "jungle": "rainforest trunks, vines, big leaves, mist",
    "ocean": "beach with waves and palm trees",
    "underwater": "under the sea: light rays, seaweed, coral, fish, bubbles",
    "desert": "sand dunes, cactus, hot sun, mesas",
    "mountains": "snowy peaks, pines, rocks",
    "arctic": "snow, ice, igloo, northern lights",
    "volcano": "smoking volcano, lava glow, dark rocks",
    "cave": "dark cave, stalactites, glowing crystals",
    "city": "city skyline, street, trees, lamp post",
    "lab": "science lab: chalkboard, bubbling beakers, microscope",
    "library": "tall bookshelves, globe, rug",
    "night": "night sky, moon, stars, campsite tent and campfire, fireflies",
}
Theme = Literal["attic", "workbench", "sunbeam", "sky", "air", "sunset", "mars", "space",
                "studio", "forest", "jungle", "ocean", "underwater", "desert", "mountains",
                "arctic", "volcano", "cave", "city", "lab", "library", "night"]


class Background(BaseModel):
    theme: Theme | None = Field(
        default=None,
        description="Environment the renderer draws: "
                    + "; ".join(f"{k} ({v})" for k, v in THEME_GUIDE.items()),
    )
    library_id: str | None = Field(default=None, description="Reuse an existing library scene")
    asset_request: str | None = Field(
        default=None, max_length=300,
        description="Description of a new background (vector style, no text)",
    )
    parallax_layers: int = Field(default=3, ge=1, le=5)


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
    shots: list[Shot] = Field(min_length=1, max_length=4)
    background: Background
    motion_graphics: list[MotionGraphic] = Field(default_factory=list)
    sfx: list[SoundEffect] = Field(default_factory=list)
    transition_out: Transition = Transition()
    educational_purpose: str = Field(max_length=200)


class StoryboardDraft(BaseModel):
    """LLM output."""

    scenes: list[StoryboardScene] = Field(min_length=6, max_length=24)


class Storyboard(BaseModel):
    schema_version: Literal["storyboard.v2"] = "storyboard.v2"
    episode_slug: str
    script_version: int
    fps: int = 30
    width: int = 1920
    height: int = 1080
    scenes: list[StoryboardScene]
    total_duration_s: float
    catalogue_version: str
    rig_version: str
