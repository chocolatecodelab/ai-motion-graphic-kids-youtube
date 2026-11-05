// Acting layer (owner: "motion is too limited"). Characters perform each line by its script
// emotion, pulse gestures with the voice loudness, and react while the other one talks.
// Pure functions of (line, frame), layered on top of the storyboard pose.
import { ARKA_EXPRESSIONS, type ArkaExpression, type ArkaPose, lerpExpression, lerpPose } from "../rig/arkaData";
import type { LipaExpression, LipaPose } from "../rig/lipa";

export interface Speech {
  speaker: string;
  emotion: string;
  lt: number; // frames since the line started
  len: number; // line length in frames
  amp: (lt: number) => number; // 0..1 voice loudness at a line-relative frame
}

const TAU = Math.PI * 2;
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (v: number) => {
  const c = clamp01(v);
  return c * c * (3 - 2 * c);
};

/** Loudness smoothed over ~5 frames (the raw mouth curve flickers per syllable). */
export const ampSmooth = (sp: Speech) => {
  let a = 0;
  for (let k = 0; k < 5; k++) a += sp.amp(sp.lt - k);
  return a / 5;
};

/** 0 -> 1 -> 0 over a line: gestures ease in at the start and settle before the end. */
const lineEnv = (sp: Speech) => smooth(sp.lt / 7) * smooth((sp.len - sp.lt) / 9);

// Storyboard poses that already say something with the arms keep them; acting then works
// through the body and head only.
const FREE_ARMS = new Set(["idle", "talk", "walk", "surprised", "think", "look_up"]);

const towards = (p: ArkaPose, patch: Partial<ArkaPose>, k: number) => lerpPose(p, { ...p, ...patch }, k);

/** Arka performs his own line. */
export const arkaSpeaking = (pose: ArkaPose, boardPose: string, sp: Speech, fps: number, seed: number): ArkaPose => {
  const env = lineEnv(sp);
  const a = ampSmooth(sp);
  const s = sp.lt / fps;
  const arms = FREE_ARMS.has(boardPose);
  const beat = Math.sin(s * TAU * 1.1 + seed); // slow alternation between gestures
  let p = { ...pose, headTilt: pose.headTilt + 3 * a * env * Math.sin(s * TAU * 1.6) };
  // Everyone: a small lift on stressed syllables (energy reads through the whole body).
  p = { ...p, rootY: p.rootY - 3.5 * a * env, squash: p.squash - 0.012 * a * env };
  switch (sp.emotion) {
    case "excited":
    case "delighted": {
      p = { ...p, rootY: p.rootY - 5 * env * Math.abs(Math.sin(s * TAU * 1.8)) ** 1.5, lean: p.lean - 1.5 * env };
      if (arms) p = towards(p, {
        handL: { x: -86, y: -96 - 30 * a }, handR: { x: 86, y: -100 - 34 * a }, handShapeL: "open", handShapeR: "open",
      }, env * 0.85);
      break;
    }
    case "surprised": {
      const hit = Math.exp(-sp.lt / (fps * 0.35)); // a quick jolt at the line start
      p = { ...p, rootX: p.rootX - 6 * hit, rootY: p.rootY - 10 * hit, lean: p.lean - 5 * hit - 2 * env };
      if (arms) p = towards(p, { handL: { x: -88, y: -122 }, handR: { x: 88, y: -122 }, handShapeL: "open", handShapeR: "open" }, env * 0.8);
      break;
    }
    case "curious": {
      p = { ...p, lean: p.lean + 3.5 * env, headTilt: p.headTilt + 6 * env };
      if (arms) p = towards(p, { handR: { x: 22, y: -108 }, handShapeR: "point" }, env * (0.5 + 0.5 * Math.max(0, beat)));
      break;
    }
    case "thoughtful": {
      p = { ...p, headTilt: p.headTilt - 5 * env + 2.5 * Math.sin(s * TAU * 0.5) * env, lean: p.lean - 1 * env };
      if (arms) p = towards(p, { handR: { x: 14, y: -110 }, handL: { x: 18, y: -62 }, handShapeL: "open" }, env * 0.8);
      break;
    }
    case "puzzled": {
      p = { ...p, headTilt: p.headTilt - 9 * env };
      if (arms) p = towards(p, { handR: { x: 60, y: -160 + 4 * Math.sin(s * TAU * 3) }, handShapeR: "open" }, env * 0.85);
      break;
    }
    case "determined": {
      const punch = Math.max(0, Math.sin(s * TAU * 1.2)) ** 2;
      p = { ...p, lean: p.lean + 3 * env, headTilt: p.headTilt - 2 * env };
      if (arms) p = towards(p, { handR: { x: 70, y: -96 - 30 * punch * a - 12 }, handShapeR: "fist" }, env * 0.85);
      break;
    }
    case "playful": {
      p = { ...p, rootX: p.rootX + 4 * Math.sin(s * TAU * 0.8) * env, headTilt: p.headTilt + 6 * Math.sin(s * TAU * 0.8) * env };
      if (arms) p = towards(p, { handL: { x: -70, y: -54 }, handR: { x: 74, y: -70 - 16 * a }, handShapeR: "open" }, env * 0.7);
      break;
    }
    default: {
      // Neutral explaining: open-hand beats that alternate between the hands with the voice.
      if (arms) {
        const r = Math.max(0, beat);
        const l = Math.max(0, -beat);
        p = towards(p, {
          handR: { x: 70 + 10 * r, y: -60 - 26 * r * (0.5 + a) }, handShapeR: "open",
          handL: { x: -66 - 8 * l, y: -40 - 20 * l * (0.5 + a) }, handShapeL: l > 0.3 ? "open" : p.handShapeL,
        }, env * 0.8);
      }
    }
  }
  return p;
};

/** Arka listens: turns toward the speaker, leans in a little, and nods now and then. */
export const arkaListening = (pose: ArkaPose, sp: Speech, fps: number, seed: number, partnerDir: number): ArkaPose => {
  const s = sp.lt / fps;
  const env = smooth(sp.lt / 10);
  const nodCycle = (s + (seed % 7) * 0.3) % 2.6;
  const nod = nodCycle < 0.5 ? Math.sin((nodCycle / 0.5) * Math.PI) ** 2 : 0;
  return {
    ...pose,
    turn: Math.max(-1, Math.min(1, pose.turn + (partnerDir < 0 ? -0.8 : 0) * env)),
    lean: pose.lean + 1.2 * env * partnerDir,
    headTilt: pose.headTilt + 5 * nod * env,
  };
};

const EMOTION_FACE: Record<string, keyof typeof ARKA_EXPRESSIONS> = {
  excited: "delighted", delighted: "delighted", surprised: "surprised", puzzled: "puzzled",
  thoughtful: "curious", curious: "curious", determined: "determined", playful: "wink",
};

/** While speaking, the face leans toward the line's emotion (the mouth keeps lip-syncing). */
export const arkaFaceActing = (e: ArkaExpression, sp: Speech | null, isSpeaker: boolean, partnerDir: number): ArkaExpression => {
  if (!sp) return e;
  if (!isSpeaker) {
    const look = partnerDir * 0.6 * smooth(sp.lt / 8);
    const eye = (st: ArkaExpression["eyeL"]) => (st.shape === "open" ? { ...st, lookX: Math.max(-1, Math.min(1, st.lookX + look)) } : st);
    return { ...e, eyeL: eye(e.eyeL), eyeR: eye(e.eyeR) };
  }
  const id = EMOTION_FACE[sp.emotion];
  if (!id) return e;
  const blended = lerpExpression(e, ARKA_EXPRESSIONS[id], 0.75 * lineEnv(sp));
  return { ...blended, mouth: e.mouth, mouthOpen: e.mouthOpen };
};

/* ------------------------------------------------------------------ Lipa */

export interface LipaActing { pose: LipaPose; rateMul: number; expression: LipaExpression }

export const lipaActing = (pose: LipaPose, e: LipaExpression, sp: Speech | null, isSpeaker: boolean,
  fps: number, t: number, still: boolean, seed: number): LipaActing => {
  const s = t / fps;
  let p = pose;
  let rateMul = 1;
  let ex = e;
  // Never a frozen hover: a lazy figure-eight drift.
  if (still) p = { ...p, x: p.x + 9 * Math.sin(s * 0.9 + seed), y: p.y + 6 * Math.sin(s * 1.8 + seed) };
  if (sp && isSpeaker) {
    const env = lineEnv(sp);
    const a = ampSmooth(sp);
    p = { ...p, y: p.y - 7 * a * env, glow: Math.max(p.glow, 0.45 + 0.55 * a * env), rot: p.rot + 5 * a * env * Math.sin(sp.lt / 3) };
    rateMul = 1 + 0.35 * a * env;
    switch (sp.emotion) {
      case "excited":
      case "delighted":
        p = { ...p, y: p.y - 10 * env * Math.abs(Math.sin((sp.lt / fps) * TAU * 1.6)) };
        rateMul += 0.4 * env;
        break;
      case "surprised": {
        const hit = Math.exp(-sp.lt / (fps * 0.35));
        p = { ...p, y: p.y - 26 * hit, flap: Math.max(p.flap, hit) };
        rateMul += 0.6 * hit;
        break;
      }
      case "puzzled":
        p = { ...p, rot: p.rot + 12 * env };
        break;
      case "thoughtful":
        rateMul *= 0.75;
        p = { ...p, rot: p.rot + 4 * env };
        break;
      case "playful":
        p = { ...p, rot: p.rot + 10 * Math.sin((sp.lt / fps) * TAU * 0.9) * env };
        break;
      default:
        break;
    }
  } else if (sp) {
    // Listening: tilt toward the speaker with a small nod every couple of seconds.
    const nodCycle = ((sp.lt / fps) + seed * 0.2) % 2.2;
    const nod = nodCycle < 0.4 ? Math.sin((nodCycle / 0.4) * Math.PI) ** 2 : 0;
    p = { ...p, rot: p.rot + 6 * nod };
    ex = { ...ex, lookX: Math.max(ex.lookX, 0.6) };
  }
  return { pose: p, rateMul, expression: ex };
};
