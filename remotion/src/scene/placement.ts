// Collision-aware placement of motion graphics: panels never cover a character's face or body.
// Pure function of (component, characters' on-screen boxes), decided once per shot so panels
// never jump mid-shot.
import { H, W } from "./layout";

export interface Box { x0: number; y0: number; x1: number; y1: number }
export interface Placement { left: number; top: number; scale: number; layout?: "row" | "column" }

const MARGIN = 56;
const CAPTION_TOP = 0.86 * H; // captions live below this line
const FREE_BOTTOM = CAPTION_TOP - 16;

// Nominal panel sizes (px at scale 1), from graphics/Graphics.tsx.
const SIZE: Record<string, { w: number; h: number }> = {
  Recap: { w: 1192, h: 380 },
  RecapColumn: { w: 380, h: 1192 },
  Label: { w: 520, h: 110 },
  WaveCompare: { w: 800, h: 360 },
  HologramPanel: { w: 820, h: 420 },
  LightRays: { w: 900, h: 520 },
  ScaleCompare: { w: 900, h: 520 },
  Orbit: { w: 720, h: 520 },
  Counter: { w: 620, h: 280 },
};
const sizeOf = (component: string) => SIZE[component] ?? { w: 820, h: 460 };

const area = (b: Box) => Math.max(0, b.x1 - b.x0) * Math.max(0, b.y1 - b.y0);
const overlap = (a: Box, b: Box) =>
  area({ x0: Math.max(a.x0, b.x0), y0: Math.max(a.y0, b.y0), x1: Math.min(a.x1, b.x1), y1: Math.min(a.y1, b.y1) });

interface Candidate { box: Box; p: Placement }

/** Fit a w x h panel into a region, keeping aspect, never larger than maxScale. */
const fit = (w: number, h: number, region: Box, maxScale: number, anchor: "left" | "right" | "top" | "center",
  layout?: "row" | "column"): Candidate | null => {
  const rw = region.x1 - region.x0;
  const rh = region.y1 - region.y0;
  if (rw < 120 || rh < 80) return null;
  const s = Math.min(maxScale, rw / w, rh / h);
  if (s < 0.38) return null; // too small to read
  const pw = w * s;
  const ph = h * s;
  const left = anchor === "left" ? region.x0 : anchor === "right" ? region.x1 - pw : region.x0 + (rw - pw) / 2;
  const top = anchor === "top" ? region.y0 : region.y0 + (rh - ph) / 2;
  return { box: { x0: left, y0: top, x1: left + pw, y1: top + ph }, p: { left, top, scale: s, layout } };
};

/**
 * Choose where a graphic goes. `chars` are the characters' screen boxes for this shot.
 * Candidates: left / right side columns beside the characters, the top band, and the centre;
 * the Recap may stack as a column. The winner has the least overlap with any character,
 * then the largest readable scale.
 */
export const placeGraphic = (component: string, chars: Box[], index = 0, maxScale = 0.8): Placement => {
  const leftEdge = Math.min(W, ...chars.map((c) => c.x0));
  const rightEdge = Math.max(0, ...chars.map((c) => c.x1));
  const topEdge = Math.min(H, ...chars.map((c) => c.y0));
  const regions = {
    left: { x0: MARGIN, y0: MARGIN, x1: Math.max(MARGIN, leftEdge - 24), y1: FREE_BOTTOM },
    right: { x0: Math.min(W - MARGIN, rightEdge + 24), y0: MARGIN, x1: W - MARGIN, y1: FREE_BOTTOM },
    top: { x0: MARGIN, y0: MARGIN, x1: W - MARGIN, y1: Math.max(MARGIN, topEdge - 20) },
    full: { x0: MARGIN, y0: MARGIN, x1: W - MARGIN, y1: FREE_BOTTOM },
  };
  const variants = component === "Recap"
    ? [{ ...sizeOf("Recap"), layout: "row" as const }, { ...sizeOf("RecapColumn"), layout: "column" as const }]
    : [{ ...sizeOf(component), layout: undefined }];

  const cands: Candidate[] = [];
  for (const v of variants) {
    for (const [name, region] of Object.entries(regions)) {
      const anchor = name === "left" ? "left" : name === "right" ? "right" : name === "top" ? "top" : "center";
      const c = fit(v.w, v.h, region, maxScale, anchor, v.layout);
      if (c) cands.push(c);
    }
  }
  if (!cands.length) return { left: W / 2 - 300, top: MARGIN, scale: 0.5 };

  const charArea = chars.reduce((s, c) => s + area(c), 0) || 1;
  const score = (c: Candidate) => {
    const hit = chars.reduce((s, ch) => s + overlap(c.box, ch), 0) / Math.min(charArea, area(c.box));
    return hit * 10 - c.p.scale; // overlap dominates; then prefer bigger panels
  };
  cands.sort((a, b) => score(a) - score(b));
  const best = cands[0];
  // Several labels stack downwards in the same slot.
  if (component === "Label" && index > 0) {
    return { ...best.p, top: Math.min(FREE_BOTTOM - 110 * best.p.scale, best.p.top + index * 120 * best.p.scale) };
  }
  return best.p;
};
