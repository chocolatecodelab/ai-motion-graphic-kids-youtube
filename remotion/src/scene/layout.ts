// World layout, character motion and camera maths. Pure functions of (shot, frame), so
// every frame renders deterministically.
import { Easing, interpolate } from "remotion";
import type { CharacterId, PlanBlocking, PlanShot } from "../types";

export const W = 1920;
export const H = 1080;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.45, 0, 0.25, 1);

// Character height in world pixels at blocking.scale = 1 (a medium figure in a wide frame).
export const BASE_HEIGHT: Record<CharacterId, number> = { kai: 0.62 * H, needle: 0.16 * H };
const DEPTH_SCALE = { background: 0.72, midground: 1, foreground: 1.22 } as const;
export const DEPTH_PARALLAX = { background: 0.75, midground: 1, foreground: 1.25 } as const;

export interface ActorState {
  character: CharacterId;
  x: number; // world px (feet / anchor)
  y: number;
  height: number; // world px
  rotate: number; // deg
  scaleX: number; // -1 to face left
  squash: number; // vertical squash for bounces
  opacity: number;
  walkPhase: number; // 0..1 cycle, 0 when standing
  portal: number; // 0..1 portal ring strength
}

const ENTER_FRAMES = 14;

const pathAt = (b: PlanBlocking, t: number) => {
  const pts = [{ x: b.x, y: b.y, scale: b.scale, frame: 0 }, ...b.path];
  if (pts.length === 1) return pts[0];
  const frames = pts.map((p) => p.frame);
  const pick = (k: "x" | "y" | "scale") =>
    interpolate(t, frames, pts.map((p) => p[k]), { ...clamp, easing: ease });
  return { x: pick("x"), y: pick("y"), scale: pick("scale"), frame: t };
};

export const actorAt = (b: PlanBlocking, t: number, shotLen: number, seed: number): ActorState => {
  const p = pathAt(b, t);
  let x = p.x * W;
  let y = p.y * H;
  let scale = p.scale * DEPTH_SCALE[b.depth];
  let rotate = 0;
  let squash = 1;
  let opacity = 1;
  let walkPhase = 0;
  let portal = 0;
  const progress = shotLen > 1 ? t / (shotLen - 1) : 0;

  switch (b.motion) {
    case "walk": walkPhase = (t / 18) % 1; y -= Math.abs(Math.sin((t / 18) * Math.PI * 2)) * 10; break;
    case "run": walkPhase = (t / 10) % 1; y -= Math.abs(Math.sin((t / 10) * Math.PI * 2)) * 18; rotate = 7; break;
    case "fly": y -= 18 + Math.sin((t + seed) / 7) * 16; rotate = 9; break;
    case "float": y -= Math.sin((t + seed) / 9) * 12; break;
    case "jump": {
      const c = (t % 26) / 26;
      y -= Math.sin(c * Math.PI) * 90;
      squash = c < 0.08 || c > 0.92 ? 0.9 : 1.03;
      break;
    }
    case "shrink": scale *= interpolate(progress, [0, 1], [1, 0.35], { ...clamp, easing: ease }); break;
    case "grow": scale *= interpolate(progress, [0, 1], [1, 1.6], { ...clamp, easing: ease }); break;
    case "spin": rotate = interpolate(progress, [0, 1], [0, 360], clamp); break;
    case "bounce": {
      const s = Math.abs(Math.sin((t + seed) / 6));
      y -= s * 26;
      squash = 0.92 + s * 0.12;
      break;
    }
    case "zip":
      x += Math.sin((t + seed) / 5.3) * 0.05 * W + Math.sin((t + seed) / 2.1) * 0.012 * W;
      y += Math.cos((t + seed) / 4.1) * 0.035 * H;
      rotate = Math.sin((t + seed) / 4) * 15;
      break;
    default: break;
  }

  const enterK = interpolate(t, [0, ENTER_FRAMES], [1, 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  const exitK = interpolate(t, [shotLen - ENTER_FRAMES, shotLen], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  const offscreen = (e: string, k: number) => {
    if (k <= 0) return;
    if (e === "from_left") x = interpolate(k, [0, 1], [x, -0.25 * W]);
    if (e === "from_right") x = interpolate(k, [0, 1], [x, 1.25 * W]);
    if (e === "from_top") y = interpolate(k, [0, 1], [y, -0.3 * H]);
    if (e === "from_bottom") y = interpolate(k, [0, 1], [y, 1.5 * H]);
    if (e === "pop") { scale *= 1 - k; opacity = 1 - k * 0.5; }
    if (e === "portal") { scale *= 1 - k; portal = Math.max(portal, k > 0 ? 1 - Math.abs(k - 0.5) : 0); }
  };
  offscreen(b.enter, enterK);
  offscreen(b.exit, exitK);

  const facing = b.facing === "left" ? -1 : 1;
  return {
    character: b.character, x, y,
    height: BASE_HEIGHT[b.character] * scale,
    rotate, scaleX: facing, squash, opacity, walkPhase, portal,
  };
};

// Screen height (fraction of frame) the focus character should fill for each shot type.
const TARGET: Record<string, number> = {
  extreme_wide: 0.24, wide: 0.55, medium: 1.12, close_up: 2.2, extreme_close_up: 4.0,
  over_shoulder: 0.95, pov: 0.7, insert: 0.6,
};

export interface CameraState { zoom: number; cx: number; cy: number; rotate: number }

const headPoint = (a: ActorState, shotType: string) => {
  // Close shots frame the face; wider shots frame the body centre.
  const k = a.character === "needle" ? 0.5
    : shotType === "close_up" || shotType === "extreme_close_up" ? 0.74 : shotType === "medium" ? 0.64 : 0.5;
  return { x: a.x, y: a.y - a.height * k };
};

export const cameraAt = (shot: PlanShot, t: number, actorsNow: ActorState[], actorsStart: ActorState[]): CameraState => {
  const len = Math.max(1, shot.end_frame - shot.start_frame);
  const p = interpolate(t, [0, len - 1], [0, 1], { ...clamp, easing: ease });
  const tracking = shot.camera_move === "follow";
  const actors = tracking ? actorsNow : actorsStart;

  const focusIds: CharacterId[] =
    shot.focus === "kai" || shot.focus === "needle" ? [shot.focus] : ["kai", "needle"];
  const focused = actors.filter((a) => focusIds.includes(a.character));
  const subjects = focused.length ? focused : actors;

  let zoom = 1;
  let cx = W / 2;
  let cy = H / 2;
  if (shot.focus === "graphic" || shot.focus === "background" || subjects.length === 0) {
    zoom = shot.shot_type === "extreme_wide" ? 0.85 : 1;
  } else {
    const target = TARGET[shot.shot_type] ?? 0.55;
    const kai = subjects.find((a) => a.character === "kai");
    const ref = kai ?? subjects[0];
    const refHeight = ref.character === "needle" ? ref.height * 3.2 : ref.height; // Needle is tiny
    zoom = (target * H) / Math.max(refHeight, 1);
    const pts = subjects.map((a) => headPoint(a, shot.shot_type));
    cx = pts.reduce((s, q) => s + q.x, 0) / pts.length;
    cy = pts.reduce((s, q) => s + q.y, 0) / pts.length;
    if (pts.length > 1) {
      const spread = Math.max(...pts.map((q) => q.x)) - Math.min(...pts.map((q) => q.x));
      zoom = Math.min(zoom, (0.72 * W) / Math.max(spread, 1));
    }
    if (shot.shot_type === "over_shoulder") cx += 0.12 * W;
  }
  zoom = Math.min(Math.max(zoom, 0.55), 4.5);

  let rotate = 0;
  switch (shot.camera_move) {
    case "zoom_in": case "dolly_in": zoom *= interpolate(p, [0, 1], [1, 1.28]); break;
    case "zoom_out": case "dolly_out": zoom *= interpolate(p, [0, 1], [1.28, 1]); break;
    case "pan_left": case "truck_left": cx += interpolate(p, [0, 1], [0.1, -0.1]) * W / zoom; break;
    case "pan_right": case "truck_right": cx += interpolate(p, [0, 1], [-0.1, 0.1]) * W / zoom; break;
    case "tilt_up": cy += interpolate(p, [0, 1], [0.12, -0.08]) * H / zoom; break;
    case "tilt_down": cy += interpolate(p, [0, 1], [-0.08, 0.12]) * H / zoom; break;
    case "crane_up": cy += interpolate(p, [0, 1], [0.1, -0.14]) * H / zoom; zoom *= interpolate(p, [0, 1], [1.08, 0.94]); break;
    case "crane_down": cy += interpolate(p, [0, 1], [-0.14, 0.1]) * H / zoom; zoom *= interpolate(p, [0, 1], [0.94, 1.08]); break;
    case "whip_pan": cx += interpolate(t, [0, 9], [0.9, 0], { ...clamp, easing: Easing.out(Easing.cubic) }) * W / zoom; break;
    case "shake": {
      const amp = interpolate(t, [0, 24], [22, 4], clamp);
      cx += Math.sin(t * 2.7) * amp / zoom;
      cy += Math.cos(t * 3.3) * amp / zoom;
      break;
    }
    case "orbit": rotate += Math.sin(p * Math.PI * 2) * 3; cx += Math.sin(p * Math.PI) * 0.05 * W / zoom; break;
    default: break;
  }

  // A low camera looks up: the subject sits higher in frame (camera centre below it).
  // A high camera looks down: the subject sits lower in frame.
  switch (shot.angle) {
    case "low": cy += 0.09 * H / zoom; break;
    case "high": cy -= 0.09 * H / zoom; break;
    case "birds_eye": cy -= 0.15 * H / zoom; break;
    case "tilted": rotate += 7; break;
    default: break;
  }
  return { zoom, cx, cy, rotate };
};
