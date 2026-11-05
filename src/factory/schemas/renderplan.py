"""renderplan.v1: frame-accurate plan the `timing` stage builds for Remotion.

Mirror of remotion/src/types.ts. Keep the two in sync.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from factory.schemas.characters import CharacterId

Theme = Literal["attic", "workbench", "sunbeam", "sky", "air", "sunset", "mars", "space",
                "studio"]


class PlanWaypoint(BaseModel):
    x: float
    y: float
    scale: float
    frame: int


class PlanBlocking(BaseModel):
    character: CharacterId
    x: float
    y: float
    scale: float
    depth: str
    facing: str
    pose: str
    expression: str
    action: str | None
    enter: str
    exit: str
    motion: str
    path: list[PlanWaypoint]


class PlanShot(BaseModel):
    start_frame: int
    end_frame: int
    shot_type: str
    angle: str
    camera_move: str
    focus: str
    blocking: list[PlanBlocking]


class PlanGraphic(BaseModel):
    component: str
    props: dict[str, Any]
    illustrative: bool
    start_frame: int
    end_frame: int


class PlanLine(BaseModel):
    line_id: str
    speaker: CharacterId
    text: str
    emotion: str
    start_frame: int
    end_frame: int
    mouth: list[float]


class PlanWord(BaseModel):
    text: str
    start_frame: int
    end_frame: int


class PlanCaption(BaseModel):
    """One on-screen caption chunk (owner decision D7), scene-relative frames."""

    speaker: CharacterId
    start_frame: int
    end_frame: int
    lines: list[list[PlanWord]] = Field(min_length=1, max_length=2)


class PlanTransition(BaseModel):
    type: str
    frames: int


class PlanScene(BaseModel):
    scene_id: str
    beat: str
    duration_frames: int
    theme: Theme
    background_description: str
    shots: list[PlanShot]
    graphics: list[PlanGraphic]
    lines: list[PlanLine]
    captions: list[PlanCaption] = Field(default_factory=list)
    transition_in: PlanTransition
    transition_out: PlanTransition


class AudioCue(BaseModel):
    line_id: str
    file: str  # relative to the content dir
    start_s: float
    duration_s: float


class SfxCue(BaseModel):
    id: str  # storyboard SFX id, or transition_<type>
    family: str  # procedural synth family (factory.media.synth)
    scene_id: str
    start_s: float


class MusicSection(BaseModel):
    scene_id: str
    mood: str  # curious | adventure | wonder | mystery | warm
    start_s: float
    end_s: float


class RenderPlan(BaseModel):
    schema_version: Literal["renderplan.v1"] = "renderplan.v1"
    episode_slug: str
    storyboard_version: int
    fps: int = 30
    width: int = 1920
    height: int = 1080
    scenes: list[PlanScene]
    scene_start_frames: list[int]
    total_frames: int
    audio: list[AudioCue]
    sfx: list[SfxCue] = Field(default_factory=list)
    music: list[MusicSection] = Field(default_factory=list)
    subtitles_srt: str | None = None
    subtitles_vtt: str | None = None
    notes: list[str] = Field(default_factory=list)
