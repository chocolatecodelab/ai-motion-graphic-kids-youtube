import { Vec, lerp, lerpV } from "./math";

/* ------------------------------------------------------------------ */
/*  ARKA — rig.v1 data model                                           */
/*  Coordinates: root space = feet on ground (0,0), y up is negative.  */
/*  Hands live in torso space (origin = hip centre, before lean).      */
/*  Feet live in root space. Everything numeric is interpolatable.     */
/* ------------------------------------------------------------------ */

export type HandShape = "fist" | "open" | "point" | "grip";
export type PropKind = "none" | "map" | "compass" | "spyglass";

export type ArkaPose = {
  rootX: number;
  rootY: number; // vertical offset (jump / bob)
  lean: number; // torso roll in degrees
  headTilt: number; // degrees
  turn: number; // -1..1 face offset (3/4 view amount)
  crouch: number; // lowers hips
  squash: number; // + squash / - stretch
  handL: Vec;
  handR: Vec;
  footL: Vec;
  footR: Vec;
  handShapeL: HandShape;
  handShapeR: HandShape;
  prop: PropKind;
  /** 0..1 prop visibility: props grow in / shrink out during blends instead of popping. */
  propScale: number;
  scarfWind: number; // 0 = hanging, 1 = flowing, 1.4 = gusty
};

export type EyeShape = "open" | "happy" | "closed" | "star";
export type EyeState = {
  shape: EyeShape;
  open: number; // 0..1 lid
  iris: number; // iris scale
  lookX: number; // -1..1
  lookY: number; // -1..1
  lower: number; // 0..1 lower lid raise (squint)
};
export type Brow = { y: number; rot: number }; // rot > 0 = inner end down (angry)
export type MouthKind =
  | "smile"
  | "grin"
  | "o"
  | "open"
  | "smirk"
  | "wavy"
  | "teeth"
  | "laugh"
  | "flat"
  | "cat"
  | "talk";
export type Extra = "none" | "sparkle" | "sweat" | "question" | "shock";

export type ArkaExpression = {
  eyeL: EyeState;
  eyeR: EyeState;
  browL: Brow;
  browR: Brow;
  mouth: MouthKind;
  mouthOpen: number; // used by "talk"
  blush: number;
  extra: Extra;
};

/* ----------------------------- POSES ------------------------------ */

const BASE: ArkaPose = {
  rootX: 0,
  rootY: 0,
  lean: 0,
  headTilt: 0,
  turn: 1,
  crouch: 0,
  squash: 0,
  handL: { x: -55, y: -22 },
  handR: { x: 55, y: -22 },
  footL: { x: -22, y: -12 },
  footR: { x: 22, y: -12 },
  handShapeL: "fist",
  handShapeR: "fist",
  prop: "none",
  propScale: 1,
  scarfWind: 0.55,
};

const p = (o: Partial<ArkaPose>): ArkaPose => ({ ...BASE, ...o });

export const ARKA_POSES = {
  idle: p({}),
  talk: p({
    handR: { x: 68, y: -58 },
    handShapeR: "open",
    headTilt: 4,
    lean: -1,
  }),
  point: p({
    handR: { x: 124, y: -106 },
    handShapeR: "point",
    handL: { x: -46, y: -28 },
    lean: 2,
    headTilt: -3,
    footL: { x: -26, y: -12 },
    footR: { x: 25, y: -12 },
    scarfWind: 0.8,
  }),
  think: p({
    handR: { x: 14, y: -110 },
    handL: { x: 18, y: -62 },
    handShapeL: "open",
    headTilt: -7,
    lean: -1,
  }),
  surprised: p({
    handL: { x: -92, y: -128 },
    handR: { x: 92, y: -128 },
    handShapeL: "open",
    handShapeR: "open",
    lean: -3,
    rootY: -6,
    footL: { x: -26, y: -12 },
    footR: { x: 26, y: -12 },
    scarfWind: 1,
  }),
  celebrate: p({
    handL: { x: -116, y: -160 },
    handR: { x: 116, y: -160 },
    rootY: -24,
    footL: { x: -27, y: -34 },
    footR: { x: 23, y: -14 },
    headTilt: -4,
    scarfWind: 1.2,
  }),
  walk: p({
    footL: { x: -19, y: -38 },
    footR: { x: 24, y: -10 },
    handL: { x: -44, y: -30 },
    handR: { x: 57, y: -14 },
    lean: 2,
    rootY: -4,
    scarfWind: 1,
  }),
  hold_map: p({
    handL: { x: -50, y: -50 },
    handR: { x: 50, y: -50 },
    handShapeL: "grip",
    handShapeR: "grip",
    prop: "map",
    headTilt: 6,
  }),
  hold_compass: p({
    handR: { x: 12, y: -58 },
    handL: { x: -10, y: -44 },
    handShapeR: "grip",
    handShapeL: "open",
    prop: "compass",
    headTilt: 8,
  }),
  look_out: p({
    handR: { x: 66, y: -170 },
    handShapeR: "grip",
    handL: { x: -46, y: -28 },
    prop: "spyglass",
    lean: -4,
    headTilt: -6,
    scarfWind: 1.1,
  }),
  // Polish: feet closer + slight squash so the knees bend forward-ish instead of splaying
  // sideways like a frog; hands rest low near the knees.
  crouch: p({
    crouch: 12,
    squash: 0.04,
    footL: { x: -28, y: -11 },
    footR: { x: 28, y: -11 },
    handL: { x: -50, y: -4 },
    handR: { x: 50, y: -4 },
    lean: 3,
    headTilt: 3,
  }),
  // Back-compat with rig v1 storyboards (Kai's `look_up`): gaze up, no spyglass.
  look_up: p({
    handL: { x: -52, y: -26 },
    handR: { x: 54, y: -24 },
    lean: -3,
    headTilt: -12,
    scarfWind: 0.7,
  }),
  wave: p({
    handR: { x: 94, y: -168 },
    handShapeR: "open",
    headTilt: 6,
    lean: -1,
  }),
  jump: p({
    rootY: -62,
    footL: { x: -28, y: -50 },
    footR: { x: 27, y: -40 },
    handL: { x: -94, y: -150 },
    handR: { x: 94, y: -150 },
    handShapeL: "open",
    handShapeR: "open",
    squash: -0.04,
    scarfWind: 1.4,
  }),
} satisfies Record<string, ArkaPose>;

export type ArkaPoseName = keyof typeof ARKA_POSES;
export const ARKA_POSE_NAMES = Object.keys(ARKA_POSES) as ArkaPoseName[];

/* --------------------------- EXPRESSIONS -------------------------- */

const E = (o: Partial<EyeState> = {}): EyeState => ({
  shape: "open",
  open: 1,
  iris: 1,
  lookX: 0.25,
  lookY: 0,
  lower: 0,
  ...o,
});
const B = (y = 0, rot = 0): Brow => ({ y, rot });

const x = (o: Partial<ArkaExpression>): ArkaExpression => ({
  eyeL: E(),
  eyeR: E(),
  browL: B(),
  browR: B(),
  mouth: "smile",
  mouthOpen: 0,
  blush: 0.35,
  extra: "none",
  ...o,
});

export const ARKA_EXPRESSIONS = {
  neutral: x({}),
  curious: x({
    eyeL: E({ lookX: 0.6, lookY: -0.3, open: 0.92 }),
    eyeR: E({ lookX: 0.6, lookY: -0.3, iris: 1.05 }),
    browL: B(1, 3),
    browR: B(-7, -9),
    mouth: "o",
    blush: 0.3,
  }),
  surprised: x({
    eyeL: E({ iris: 0.72, lookX: 0 }),
    eyeR: E({ iris: 0.72, lookX: 0 }),
    browL: B(-8, -4),
    browR: B(-8, -4),
    mouth: "open",
    blush: 0.25,
    extra: "shock",
  }),
  delighted: x({
    eyeL: E({ shape: "happy" }),
    eyeR: E({ shape: "happy" }),
    browL: B(-4, -5),
    browR: B(-4, -5),
    mouth: "grin",
    blush: 0.75,
    extra: "sparkle",
  }),
  puzzled: x({
    eyeL: E({ open: 0.55, lower: 0.25, lookX: -0.2 }),
    eyeR: E({ lookX: -0.2, lookY: -0.3 }),
    browL: B(2, 10),
    browR: B(-7, -7),
    mouth: "wavy",
    blush: 0.2,
    extra: "question",
  }),
  determined: x({
    eyeL: E({ open: 0.78, lower: 0.15, lookX: 0.4 }),
    eyeR: E({ open: 0.78, lower: 0.15, lookX: 0.4 }),
    browL: B(2, 16),
    browR: B(2, 16),
    mouth: "teeth",
    blush: 0.2,
  }),
  worried: x({
    eyeL: E({ iris: 0.9, lookY: 0.3, lookX: -0.1 }),
    eyeR: E({ iris: 0.9, lookY: 0.3, lookX: -0.1 }),
    browL: B(-4, -14),
    browR: B(-4, -14),
    mouth: "wavy",
    blush: 0.3,
    extra: "sweat",
  }),
  laughing: x({
    eyeL: E({ shape: "happy" }),
    eyeR: E({ shape: "happy" }),
    browL: B(-5, -6),
    browR: B(-5, -6),
    mouth: "laugh",
    blush: 0.85,
  }),
  wink: x({
    eyeL: E({ lookX: 0.4 }),
    eyeR: E({ shape: "happy" }),
    browL: B(-2, 0),
    browR: B(1, 4),
    mouth: "cat",
    blush: 0.6,
    extra: "sparkle",
  }),
  awe: x({
    eyeL: E({ shape: "star", iris: 1.08, lookY: -0.2 }),
    eyeR: E({ shape: "star", iris: 1.08, lookY: -0.2 }),
    browL: B(-7, -6),
    browR: B(-7, -6),
    mouth: "o",
    mouthOpen: 1,
    blush: 0.7,
    extra: "sparkle",
  }),
} satisfies Record<string, ArkaExpression>;

export type ArkaExpressionName = keyof typeof ARKA_EXPRESSIONS;
export const ARKA_EXPRESSION_NAMES = Object.keys(
  ARKA_EXPRESSIONS,
) as ArkaExpressionName[];

/* --------------------------- INTERPOLATION ------------------------ */

/** Prop crossfade: the same prop blends its scale; a different prop shrinks out, then grows in. */
const propBlend = (a: ArkaPose, b: ArkaPose, k: number): Pick<ArkaPose, "prop" | "propScale"> => {
  if (a.prop === b.prop) return { prop: a.prop, propScale: lerp(a.propScale, b.propScale, k) };
  return k < 0.5
    ? { prop: a.prop, propScale: a.propScale * (1 - smooth(k * 2)) }
    : { prop: b.prop, propScale: b.propScale * smooth((k - 0.5) * 2) };
};
const smooth = (k: number) => {
  const c = Math.min(1, Math.max(0, k));
  return c * c * (3 - 2 * c);
};

export const lerpPose = (a: ArkaPose, b: ArkaPose, k: number): ArkaPose => ({
  ...propBlend(a, b, k),
  rootX: lerp(a.rootX, b.rootX, k),
  rootY: lerp(a.rootY, b.rootY, k),
  lean: lerp(a.lean, b.lean, k),
  headTilt: lerp(a.headTilt, b.headTilt, k),
  turn: lerp(a.turn, b.turn, k),
  crouch: lerp(a.crouch, b.crouch, k),
  squash: lerp(a.squash, b.squash, k),
  handL: lerpV(a.handL, b.handL, k),
  handR: lerpV(a.handR, b.handR, k),
  footL: lerpV(a.footL, b.footL, k),
  footR: lerpV(a.footR, b.footR, k),
  handShapeL: k < 0.5 ? a.handShapeL : b.handShapeL,
  handShapeR: k < 0.5 ? a.handShapeR : b.handShapeR,
  scarfWind: lerp(a.scarfWind, b.scarfWind, k),
});

/**
 * Procedural walk cycle (front 3/4 view). phase in [0,1). Polished: every curve is smooth
 * (no |sin| cusps or max(0,·) pops):
 * - foot lift = sin² over its swing half (zero velocity at lift-off and contact);
 * - body bob = sin²: lowest at contact, highest at passing;
 * - hips shift over the stance foot, a small squash on contact, steady forward lean;
 * - arms counter-swing smoothly against the legs; the head counter-rolls the torso.
 */
export const walkPose = (phase: number, stride = 1): ArkaPose => {
  const a = phase * Math.PI * 2;
  const s = Math.sin(a);
  const liftL = s > 0 ? s * s : 0;
  const liftR = s < 0 ? s * s : 0;
  const passing = s * s; // 0 at contacts, 1 at passing positions
  const armFwdL = (1 - s) / 2; // left arm forward while the right leg swings
  const armFwdR = (1 + s) / 2;
  return {
    ...BASE,
    rootX: 2.6 * s * stride,
    rootY: -5.5 * passing * stride,
    squash: 0.022 * Math.cos(2 * a) * stride,
    lean: 2.5 + 1.4 * s * stride,
    headTilt: 1 - 1.2 * s * stride,
    footL: { x: -21 + 4 * Math.cos(a), y: -12 - 30 * liftL * stride },
    footR: { x: 21 - 4 * Math.cos(a), y: -12 - 30 * liftR * stride },
    handL: { x: -51 + 7 * armFwdL * stride, y: -18 - 15 * armFwdL * stride },
    handR: { x: 51 + 7 * armFwdR * stride, y: -18 - 15 * armFwdR * stride },
    scarfWind: 1.05,
  };
};
