import { ARKA_EXPRESSIONS, ArkaExpression, ArkaPoseName } from "./arkaData";

/** Default facial expression paired with each body pose (used by the board + playground). */
export const POSE_FACE: Record<ArkaPoseName, ArkaExpression> = {
  idle: ARKA_EXPRESSIONS.neutral,
  talk: { ...ARKA_EXPRESSIONS.neutral, mouth: "talk", mouthOpen: 0.6, blush: 0.4 },
  point: ARKA_EXPRESSIONS.determined,
  think: { ...ARKA_EXPRESSIONS.curious, mouth: "smirk", eyeL: { ...ARKA_EXPRESSIONS.curious.eyeL, lookY: -0.8, lookX: 0.3 }, eyeR: { ...ARKA_EXPRESSIONS.curious.eyeR, lookY: -0.8, lookX: 0.3 } },
  surprised: ARKA_EXPRESSIONS.surprised,
  celebrate: { ...ARKA_EXPRESSIONS.laughing, extra: "sparkle" },
  walk: { ...ARKA_EXPRESSIONS.neutral, mouth: "grin", blush: 0.45 },
  hold_map: { ...ARKA_EXPRESSIONS.curious, eyeL: { ...ARKA_EXPRESSIONS.curious.eyeL, lookY: 0.8, lookX: 0 }, eyeR: { ...ARKA_EXPRESSIONS.curious.eyeR, lookY: 0.8, lookX: 0 }, mouth: "smile" },
  hold_compass: { ...ARKA_EXPRESSIONS.determined, mouth: "smirk", eyeL: { ...ARKA_EXPRESSIONS.determined.eyeL, lookY: 0.9, lookX: 0 }, eyeR: { ...ARKA_EXPRESSIONS.determined.eyeR, lookY: 0.9, lookX: 0 } },
  look_out: { ...ARKA_EXPRESSIONS.determined, mouth: "grin", eyeR: { ...ARKA_EXPRESSIONS.determined.eyeR, shape: "closed" } },
  crouch: { ...ARKA_EXPRESSIONS.determined, mouth: "smirk" },
  wave: ARKA_EXPRESSIONS.delighted,
  jump: { ...ARKA_EXPRESSIONS.awe, mouth: "laugh" },
  look_up: { ...ARKA_EXPRESSIONS.awe, eyeL: { ...ARKA_EXPRESSIONS.awe.eyeL, lookY: -0.9 }, eyeR: { ...ARKA_EXPRESSIONS.awe.eyeR, lookY: -0.9 } },
};
