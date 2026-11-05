// renderplan.v1: one scene of the frame-accurate render plan produced by the Python
// `timing` stage (src/factory/schemas/renderplan.py). Keep the two in sync.

export type CharacterId = "arka" | "lipa";
export type ShotType =
  | "extreme_wide" | "wide" | "medium" | "close_up" | "extreme_close_up"
  | "over_shoulder" | "pov" | "insert";
export type Angle = "eye_level" | "low" | "high" | "birds_eye" | "tilted";
export type CameraMove =
  | "static" | "zoom_in" | "zoom_out" | "dolly_in" | "dolly_out" | "pan_left" | "pan_right"
  | "tilt_up" | "tilt_down" | "truck_left" | "truck_right" | "follow" | "whip_pan"
  | "crane_up" | "crane_down" | "shake" | "orbit";
export type Depth = "foreground" | "midground" | "background";
export type Motion =
  | "none" | "walk" | "run" | "fly" | "float" | "jump" | "shrink" | "grow" | "spin"
  | "bounce" | "zip";
export type Entrance = "none" | "from_left" | "from_right" | "from_top" | "from_bottom" | "pop" | "portal";
export type TransitionType = "compass_portal" | "wipe" | "cut" | "zoom_through" | "fade" | "whip";
export type Theme =
  | "attic" | "workbench" | "sunbeam" | "sky" | "air" | "sunset" | "mars" | "space" | "studio"
  | "forest" | "jungle" | "ocean" | "underwater" | "desert" | "mountains" | "arctic" | "volcano"
  | "cave" | "city" | "lab" | "library" | "night";

export interface PlanWaypoint { x: number; y: number; scale: number; frame: number }

export interface PlanBlocking {
  character: CharacterId;
  x: number; y: number; scale: number;
  depth: Depth;
  facing: "left" | "right" | "camera";
  pose: string; expression: string; action: string | null;
  enter: Entrance; exit: Entrance; motion: Motion;
  path: PlanWaypoint[];
}

export interface PlanShot {
  start_frame: number; end_frame: number; // scene-relative, end exclusive
  shot_type: ShotType; angle: Angle; camera_move: CameraMove;
  focus: CharacterId | "both" | "graphic" | "background";
  blocking: PlanBlocking[];
}

export interface PlanGraphic {
  component: string;
  props: Record<string, unknown>;
  illustrative: boolean;
  start_frame: number; end_frame: number;
}

export interface PlanLine {
  line_id: string; speaker: CharacterId; text: string; emotion: string;
  start_frame: number; end_frame: number;
  mouth: number[]; // 0..1 openness per frame of the line
}

export interface PlanWord { text: string; start_frame: number; end_frame: number }

export interface PlanCaption {
  speaker: CharacterId;
  start_frame: number; end_frame: number;
  lines: PlanWord[][];
}

export interface PlanTransition { type: TransitionType; frames: number }

export interface PlanScene {
  scene_id: string;
  beat: string;
  duration_frames: number;
  theme: Theme;
  background_description: string;
  shots: PlanShot[];
  graphics: PlanGraphic[];
  lines: PlanLine[];
  captions?: PlanCaption[];
  transition_in: PlanTransition;
  transition_out: PlanTransition;
}

export interface SceneProps { scene: PlanScene; [key: string]: unknown }
