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
  if (s < 0.55) return null; // too small to read on a phone
  const pw = w * s;
  const ph = h * s;
  const left = anchor === "left" ? region.x0 : anchor === "right" ? region.x1 - pw : region.x0 + (rw - pw) / 2;
  const top = anchor === "top" ? region.y0 : region.y0 + (rh - ph) / 2;
  return { box: { x0: left, y0: top, x1: left + pw, y1: top + ph }, p: { left, top, scale: s, layout } };
};

export interface Placed extends Placement { box: Box }

/**
 * Choose where a graphic goes. `chars` are the characters' screen boxes for this shot (Arka's
 * face box is listed twice, so it weighs double); `obstacles` are panels already on screen.
 * Candidates: side columns beside the characters, the top band, the centre, and the two top
 * corners (always available, so a close-up gets a corner panel over the hat brim, never one
 * over the face). The winner has the least weighted overlap, then the largest readable scale.
 */
export const placeGraphic = (component: string, chars: Box[], index = 0, maxScale = 0.8,
  obstacles: Box[] = []): Placed => {
  const leftEdge = Math.min(W, ...chars.map((c) => c.x0));
  const rightEdge = Math.max(0, ...chars.map((c) => c.x1));
  const topEdge = Math.min(H, ...chars.map((c) => c.y0));
  const regions: Record<string, Box> = {
    left: { x0: MARGIN, y0: MARGIN, x1: Math.max(MARGIN, leftEdge - 24), y1: FREE_BOTTOM },
    right: { x0: Math.min(W - MARGIN, rightEdge + 24), y0: MARGIN, x1: W - MARGIN, y1: FREE_BOTTOM },
    top: { x0: MARGIN, y0: MARGIN, x1: W - MARGIN, y1: Math.max(MARGIN, topEdge - 20) },
    full: { x0: MARGIN, y0: MARGIN, x1: W - MARGIN, y1: FREE_BOTTOM },
    cornerL: { x0: MARGIN, y0: MARGIN, x1: 0.42 * W, y1: 0.42 * H },
    cornerR: { x0: 0.58 * W, y0: MARGIN, x1: W - MARGIN, y1: 0.42 * H },
  };
  const variants = component === "Recap"
    ? [{ ...sizeOf("Recap"), layout: "row" as const }, { ...sizeOf("RecapColumn"), layout: "column" as const }]
    : [{ ...sizeOf(component), layout: undefined }];

  const cands: Candidate[] = [];
  for (const v of variants) {
    for (const [name, region] of Object.entries(regions)) {
      const anchor = name === "left" || name === "cornerL" ? "left"
        : name === "right" || name === "cornerR" ? "right" : name === "top" ? "top" : "center";
      const c = fit(v.w, v.h, region, maxScale, anchor, v.layout);
      if (c) cands.push(c);
    }
  }
  if (!cands.length) {
    const v = variants[0];
    const sc = 0.55;
    const box = { x0: MARGIN, y0: MARGIN, x1: MARGIN + v.w * sc, y1: MARGIN + v.h * sc };
    return { left: MARGIN, top: MARGIN, scale: sc, layout: v.layout, box };
  }

  const score = (c: Candidate) => {
    const a = area(c.box) || 1;
    const hitChars = chars.reduce((s, ch) => s + overlap(c.box, ch), 0) / a;
    const hitPanels = obstacles.reduce((s, ob) => s + overlap(c.box, ob), 0) / a;
    return hitChars * 10 + hitPanels * 20 - c.p.scale; // never stack panels; then protect faces
  };
  cands.sort((a, b) => score(a) - score(b));
  const best = cands[0];
  // Several labels stack downwards in the same slot.
  if (component === "Label" && index > 0) {
    const top = Math.min(FREE_BOTTOM - 110 * best.p.scale, best.p.top + index * 120 * best.p.scale);
    return { ...best.p, top, box: { ...best.box, y0: top, y1: top + (best.box.y1 - best.box.y0) } };
  }
  return { ...best.p, box: best.box };
};
