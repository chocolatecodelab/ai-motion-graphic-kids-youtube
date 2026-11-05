// Storyboard blocking -> Arka / Lipa rig state. Pure functions of (blocking, frame), so every
// frame renders deterministically and a scene clip can be re-rendered from any frame.
//
// Smoothness rules (Character Bible v2, "Motion"):
// - pose changes between shots blend with a small overshoot (POSE_EASE), never snap;
// - every action eases in, and loops use sin / sin² curves (no |sin| cusps, no max(0,·) pops);
// - the head trails the body (overlap), derived from the pose a few frames earlier;
// - standing characters keep a gentle weight shift so they never freeze.
import { Easing } from "remotion";
import {
  ARKA_EXPRESSIONS,
  ARKA_POSES,
  type ArkaExpression,
  type ArkaPose,
  type ArkaPoseName,
  lerpExpression,
  lerpPose,
  walkPose,
} from "../rig/arkaData";
import { rand } from "../rig/math";
import {
  flightAt,
  lerpLipa,
  LIPA_EXPRESSIONS,
  LIPA_POSES,
  type LipaExpression,
  type LipaPose,
} from "../rig/lipa";
import { POSE_FACE } from "../rig/presets";
import { arkaFaceActing, arkaListening, arkaSpeaking, lipaActing, type Speech } from "./acting";
import type { PlanBlocking } from "../types";

export const POSE_EASE = Easing.bezier(0.34, 1.32, 0.64, 1);
const BLEND_FRAMES = 10;
const ACTION_IN = 8;

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (v: number) => {
  const c = clamp01(v);
  return c * c * (3 - 2 * c);
};
const TAU = Math.PI * 2;

/* ------------------------------ ids -------------------------------- */

// Rig v1 (Kai/Needle) IDs still found in older storyboards -> rig v2 equivalents.
const ARKA_EXPR_ALIAS: Record<string, string> = { worried_lite: "worried" };
const LIPA_POSE_ALIAS: Record<string, keyof typeof LIPA_POSES> = {
  zip: "flap",
  glow: "float",
  spin: "loop",
  peek: "perch",
  bounce: "flap",
};

export const arkaPoseFor = (name: string): ArkaPose =>
  (ARKA_POSES as Record<string, ArkaPose>)[name] ?? ARKA_POSES.idle;

export const arkaExpressionFor = (name: string, pose: string): ArkaExpression => {
  const id = ARKA_EXPR_ALIAS[name] ?? name;
  const e = (ARKA_EXPRESSIONS as Record<string, ArkaExpression>)[id] ?? ARKA_EXPRESSIONS.neutral;
  // Poses that look somewhere specific (down at the map, up at the sky) keep that gaze.
  const face = POSE_FACE[pose as ArkaPoseName];
  if (face && ["hold_map", "hold_compass", "think", "look_up"].includes(pose)) {
    return { ...e, eyeL: { ...e.eyeL, lookX: face.eyeL.lookX, lookY: face.eyeL.lookY }, eyeR: { ...e.eyeR, lookX: face.eyeR.lookX, lookY: face.eyeR.lookY } };
  }
  return e;
};

const lipaPoseFor = (name: string): LipaPose => {
  const id = (LIPA_POSE_ALIAS[name] ?? name) as keyof typeof LIPA_POSES;
  // "loop" is a motion (an eased somersault, see lipaStateAt), never a held upside-down pose.
  const base = id === "loop" ? LIPA_POSES.flap : LIPA_POSES[id] ?? LIPA_POSES.float;
  return name === "glow" ? { ...base, glow: 1 } : base;
};

export const lipaExpressionFor = (name: string): LipaExpression => {
  const id = name === "worried_lite" ? "worried" : name;
  return (LIPA_EXPRESSIONS as Record<string, LipaExpression>)[id] ?? LIPA_EXPRESSIONS.neutral;
};

/* ------------------------------ Arka -------------------------------- */

/** A hop with anticipation, airtime and a landing squash. c in [0,1). */
const hop = (pose: ArkaPose, c: number): ArkaPose => {
  const PRE = 0.18;
  const LAND = 0.82;
  if (c < PRE) {
    const s = Math.sin((Math.PI * c) / PRE);
    return { ...pose, crouch: pose.crouch + 14 * s, squash: pose.squash + 0.05 * s };
  }
  if (c < LAND) {
    const u = (c - PRE) / (LAND - PRE);
    const air = Math.sin(Math.PI * u);
    const p = lerpPose(pose, ARKA_POSES.jump, air);
    return {
      ...p,
      prop: pose.prop,
      propScale: pose.propScale,
      rootY: pose.rootY - 58 * 4 * u * (1 - u),
      squash: -0.035 * Math.sin(TAU * u) ** 2,
    };
  }
  const v = Math.sin((Math.PI * (c - LAND)) / (1 - LAND));
  return { ...pose, crouch: pose.crouch + 12 * v, squash: pose.squash + 0.06 * v };
};

const towards = (pose: ArkaPose, patch: Partial<ArkaPose>, k: number): ArkaPose =>
  lerpPose(pose, { ...pose, ...patch }, k);

const applyArkaAction = (pose: ArkaPose, action: string | null, t: number, fps: number): ArkaPose => {
  if (!action) return pose;
  const s = t / fps;
  const env = smooth(t / ACTION_IN);
  switch (action) {
    case "wave": {
      const w = s * TAU * 1.5;
      return towards(pose, {
        handR: { x: 92 + 9 * Math.sin(w), y: -170 + 5 * Math.cos(w * 2) },
        handShapeR: "open",
        headTilt: 6 + 1.5 * Math.sin(w),
      }, env);
    }
    case "nod":
      return { ...pose, headTilt: pose.headTilt + 7 * env * Math.sin(s * Math.PI * 1.7) ** 2 };
    case "jump":
      return hop(pose, ((t % 26) + 26) % 26 / 26);
    case "gasp":
      return towards(pose, { ...ARKA_POSES.surprised, prop: pose.prop, propScale: pose.propScale }, POSE_EASE(clamp01(t / 7)));
    case "look_around":
      return { ...pose, turn: pose.turn + (Math.cos(s * TAU / 2.8) - 1) * env, headTilt: pose.headTilt + 3 * Math.sin(s * TAU / 2.8) * env };
    case "tap_compass": {
      const tap = Math.sin(s * Math.PI * 2.4) ** 2;
      return towards(pose, {
        ...ARKA_POSES.hold_compass,
        handL: { x: -2, y: -54 - 7 * tap },
      }, env);
    }
    case "shrug": {
      const k = Math.sin(Math.PI * clamp01(s / 1.3));
      return towards(pose, {
        handL: { x: -84, y: -66 },
        handR: { x: 84, y: -66 },
        handShapeL: "open",
        handShapeR: "open",
        headTilt: 7,
        crouch: -3,
      }, k);
    }
    case "scratch_head": {
      const sc = Math.sin(s * TAU * 3);
      return towards(pose, { handR: { x: 60, y: -160 + 4 * sc }, handShapeR: "open", headTilt: -6 }, env);
    }
    default:
      return pose;
  }
};

// Poses whose hands carry meaning (a gesture or a prop) keep their arms while walking.
const ARMS_BUSY = new Set(["talk", "point", "hold_map", "hold_compass", "look_out", "wave", "think"]);

export interface ArkaCtx {
  b: PlanBlocking;
  prev?: PlanBlocking; // the same character in the previous shot of this scene
  len: number;
  fps: number;
  seed: number;
  talking: boolean;
  /** Arka: cumulative distance walked along his facing, in rig units, per shot frame. */
  travel?: number[];
  /** Lipa: on-screen velocity in world px per frame. */
  vel?: { x: number; y: number };
  /** Lipa: which way she should face at frame t (1 right, -1 left): travel, storyboard, partner. */
  facingAt?: (t: number) => 1 | -1;
  /** The line being spoken at shot frame t (any speaker), for acting and listening. */
  speechAt?: (t: number) => Speech | null;
  /** Direction of the other character on screen (-1 left, 1 right, 0 none). */
  partnerDir?: number;
}

const sampleAt = (arr: number[], t: number) => arr[Math.max(0, Math.min(arr.length - 1, Math.round(t)))];

// Gait constants: step length (rig units) and the cadence used for walking in place.
const GAIT = { walk: { step: 40, frames: 18, stride: 1 }, run: { step: 60, frames: 11, stride: 1.3 } } as const;

/** Arka's body pose at shot-relative frame t. */
export const arkaPoseAt = (ctx: ArkaCtx, t: number): ArkaPose => {
  const { b, prev, fps, seed, talking } = ctx;
  let pose = arkaPoseFor(b.pose);
  if (prev && prev.pose !== b.pose) {
    pose = lerpPose(arkaPoseFor(prev.pose), pose, POSE_EASE(clamp01(t / BLEND_FRAMES)));
  }
  const s = t / fps;

  if (b.motion === "walk" || b.motion === "run") {
    const run = b.motion === "run";
    const g = run ? GAIT.run : GAIT.walk;
    const tr = ctx.travel;
    const moving = tr !== undefined && Math.abs(tr[tr.length - 1] - tr[0]) > 30;
    // Moving along a path: the step phase follows the distance covered, so planted feet never
    // slide, and the gait fades in/out with the path's own ease (start, stop).
    const dist = moving ? sampleAt(tr, t) : 0;
    const speed = moving ? Math.abs(sampleAt(tr, t + 2) - sampleAt(tr, t - 2)) / 4 : 0;
    const weight = moving ? smooth(speed / ((2 * g.step) / g.frames * 0.55)) : 1;
    const w = moving ? walkPose(dist / (2 * g.step), g.stride, g.step) : walkPose(t / g.frames, g.stride);
    const busy = ARMS_BUSY.has(b.pose);
    const stand = pose;
    pose = {
      ...w,
      lean: w.lean + (run ? 5 : 0),
      handL: busy ? pose.handL : w.handL,
      handR: busy ? pose.handR : w.handR,
      handShapeL: busy ? pose.handShapeL : w.handShapeL,
      handShapeR: busy ? pose.handShapeR : w.handShapeR,
      prop: pose.prop,
      propScale: pose.propScale,
      headTilt: w.headTilt + pose.headTilt * 0.5,
    };
    if (weight < 0.999) pose = lerpPose(stand, pose, weight);
  } else if (b.motion === "jump" || b.motion === "bounce") {
    const period = b.motion === "jump" ? 26 : 18;
    pose = hop(pose, (((t + seed) % period) + period) % period / period);
  } else {
    // Idle life: slow weight shift, so a standing character is never a still frame.
    const ws = Math.sin(s * TAU * 0.23 + seed);
    pose = { ...pose, rootX: pose.rootX + 1.6 * ws, lean: pose.lean + 0.7 * ws, headTilt: pose.headTilt + 0.8 * Math.sin(s * TAU * 0.17 + seed * 0.5) };
  }

  // Acting: perform the current line by its emotion, or listen to the other character.
  const sp = ctx.speechAt?.(t) ?? null;
  if (sp) {
    pose = sp.speaker === b.character
      ? arkaSpeaking(pose, b.pose, sp, fps, seed)
      : arkaListening(pose, sp, fps, seed, ctx.partnerDir ?? 0);
  } else if (talking) {
    const g = Math.sin(s * TAU * 0.9 + seed);
    const g2 = Math.sin(s * TAU * 1.7 + seed * 1.3);
    pose = {
      ...pose,
      headTilt: pose.headTilt + 1.8 * g2,
      handR: b.pose === "talk" || b.pose === "idle" ? { x: pose.handR.x + 4 * g, y: pose.handR.y - 5 * g2 } : pose.handR,
    };
  }

  return applyArkaAction(pose, b.action, t, fps);
};

/** Follow-through: the head lags behind vertical and rolling body motion. */
export const arkaOverlap = (ctx: ArkaCtx, t: number) => {
  if (t < 3) return { y: 0, tilt: 0 };
  const now = arkaPoseAt(ctx, t);
  const back2 = arkaPoseAt(ctx, t - 2);
  const back3 = arkaPoseAt(ctx, t - 3);
  // The head (and backpack) keep where the body was a moment ago: delayed displacement.
  return { y: (back2.rootY - now.rootY) * 0.6, tilt: (back3.lean - now.lean) * 0.7 };
};

export const arkaFaceAt = (ctx: ArkaCtx, t: number, mouth: number): ArkaExpression => {
  const { b, prev } = ctx;
  let e = arkaExpressionFor(b.expression, b.pose);
  if (prev && prev.expression !== b.expression) {
    e = lerpExpression(arkaExpressionFor(prev.expression, prev.pose), e, smooth(t / 8));
  }
  if (!FIXED_GAZE.has(b.pose) && b.action !== "look_around") e = withGlances(e, t / ctx.fps, ctx.seed);
  if (b.action === "gasp") e = { ...ARKA_EXPRESSIONS.surprised };
  if (b.action === "look_around") {
    const look = Math.sin((t / ctx.fps) * TAU / 2.8);
    e = { ...e, eyeL: { ...e.eyeL, lookX: look }, eyeR: { ...e.eyeR, lookX: look } };
  }
  const sp = ctx.speechAt?.(t) ?? null;
  e = arkaFaceActing(e, sp, sp?.speaker === b.character, ctx.partnerDir ?? 0);
  if (ctx.talking) {
    // Lip-sync: the open mouth follows the voice amplitude curve; closed between syllables.
    e = { ...e, mouth: mouth > 0.06 ? "talk" : e.mouth === "talk" ? "smile" : e.mouth, mouthOpen: Math.min(1, mouth * 1.15) };
  }
  return e;
};

// Poses whose gaze is the point of the pose (map, compass, sky) keep their eyes still.
const FIXED_GAZE = new Set(["hold_map", "hold_compass", "look_up", "look_out", "think"]);

/**
 * Small eye glances (saccades): every 1.6-2.8 s the eyes shift slightly and hold, moving over
 * about 4 frames. Real eyes never stare perfectly still, so this keeps faces alive.
 */
const glanceAt = (s: number, seed: number) => {
  const segLen = (n: number) => 1.6 + 1.2 * rand(n * 3 + seed);
  let start = 0;
  let n = 0;
  while (start + segLen(n) <= s && n < 400) start += segLen(n++);
  const target = (i: number) => (i <= 0 ? { x: 0, y: 0 } : { x: (rand(i * 7 + seed) - 0.5) * 0.55, y: (rand(i * 11 + seed) - 0.5) * 0.3 });
  const k = smooth((s - start) / 0.13);
  const a = target(n - 1);
  const b = target(n);
  return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k };
};

const withGlances = (e: ArkaExpression, s: number, seed: number): ArkaExpression => {
  const g = glanceAt(s, seed);
  const eye = (st: ArkaExpression["eyeL"]) =>
    st.shape === "open" ? { ...st, lookX: Math.max(-1, Math.min(1, st.lookX + g.x)), lookY: Math.max(-1, Math.min(1, st.lookY + g.y)) } : st;
  return { ...e, eyeL: eye(e.eyeL), eyeR: eye(e.eyeR) };
};

/* ------------------------------ Lipa -------------------------------- */

export interface LipaState {
  facing: number; // -1..1, smoothed so turns read as a paper flip, not a pop
  pose: LipaPose;
  flapTip: number;
  bob: number;
  expression: LipaExpression;
}

export const lipaStateAt = (ctx: ArkaCtx, t: number, mouth: number): LipaState => {
  const { b, prev, fps, seed, talking } = ctx;
  const s = t / fps;
  let pose = lipaPoseFor(b.pose);
  if (prev && prev.pose !== b.pose) {
    pose = lerpLipa(lipaPoseFor(prev.pose), pose, POSE_EASE(clamp01(t / BLEND_FRAMES)));
  }
  const id = LIPA_POSE_ALIAS[b.pose] ?? b.pose;
  const sp = ctx.speechAt?.(t) ?? null;
  const acted = lipaActing(pose, lipaExpressionFor(b.expression), sp, sp?.speaker === b.character, fps, t,
    (b.motion === "none" || b.motion === "float") && id !== "perch", seed);
  pose = acted.pose;
  // Wingbeat strength by pose: perched/gliding wings mostly rest, flying wings beat fully.
  const strength = id === "perch" ? 0 : id === "glide" ? 0.18 : id === "dive" ? 0.35 : 1;
  const vy = ctx.vel?.y ?? 0;
  // Climbing beats faster; gliding down beats slower.
  const climb = Math.max(-0.3, Math.min(0.5, -vy * 0.035));
  const rate = (b.pose === "zip" || b.motion === "zip" ? 3.6 : id === "flap" ? 3 : 2.4) * (1 + climb) * acted.rateMul;
  const fl = flightAt(s + seed * 0.37, rate, 1);
  const flap = pose.flap * (1 - strength) + fl.flap * strength;
  const flapTip = pose.flap * (1 - strength) + fl.flapTip * strength;
  // Pitch into the motion: nose down when dropping, nose up when climbing.
  pose = { ...pose, flap, rot: pose.rot + Math.max(-22, Math.min(22, vy * 1.3)) };
  if (id === "loop") {
    // A full somersault eased in and out, every 4.5 s, upright in between.
    const period = Math.round(fps * 4.5);
    const local = (((t - 6) % period) + period) % period;
    pose = { ...pose, rot: pose.rot - 360 * smooth(local / (fps * 1.1)) };
  }
  // Facing: average the target over the last 8 frames -> a smooth turn through edge-on.
  let facing = 0;
  for (let k = 0; k < 8; k++) facing += ctx.facingAt ? ctx.facingAt(t - k) : 1;
  facing /= 8;

  let expression = acted.expression;
  const env = smooth(t / ACTION_IN);
  switch (b.action) {
    case "sparkle":
      pose = { ...pose, glow: Math.max(pose.glow, 0.9 * env) };
      expression = { ...expression, extra: "sparkle" };
      break;
    case "loop_the_loop":
      pose = { ...pose, rot: pose.rot - 360 * smooth(clamp01((t - 4) / (fps * 1.1))) };
      break;
    case "dim":
      pose = { ...pose, glow: pose.glow * (1 - 0.8 * env) };
      break;
    case "flash":
      pose = { ...pose, glow: Math.max(pose.glow, Math.sin(Math.PI * clamp01(t / 14))) };
      break;
    case "wiggle":
      pose = { ...pose, rot: pose.rot + 9 * Math.sin(s * TAU * 2.2) * env };
      break;
    default:
      break;
  }
  if (talking) expression = { ...expression, beak: Math.max(expression.beak * 0.4, Math.min(1, mouth * 1.2)) };
  return { facing, pose, flapTip, bob: fl.bob * strength, expression };
};

/** Natural blink: about every 3-4 s, offset per character, 4-frame close/open. */
export const blinkAt = (frame: number, seed: number) => {
  const cycle = 101 + (seed % 23);
  const f = ((frame + seed * 7) % cycle + cycle) % cycle;
  return f < 5 ? Math.abs(f - 2) / 2.5 : 1;
};
