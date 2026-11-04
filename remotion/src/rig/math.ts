export type Vec = { x: number; y: number };

export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export const lerpV = (a: Vec, b: Vec, k: number): Vec => ({
  x: lerp(a.x, b.x, k),
  y: lerp(a.y, b.y, k),
});
export const clamp = (v: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, v));
export const deg = (rad: number) => (rad * 180) / Math.PI;
export const rad = (d: number) => (d * Math.PI) / 180;

export const rotateAround = (p: Vec, c: Vec, degrees: number): Vec => {
  const r = rad(degrees);
  const dx = p.x - c.x;
  const dy = p.y - c.y;
  return {
    x: c.x + dx * Math.cos(r) - dy * Math.sin(r),
    y: c.y + dx * Math.sin(r) + dy * Math.cos(r),
  };
};

/**
 * Two-bone IK. Returns the middle joint (elbow/knee) and the reachable end point.
 * `bias` picks which of the two solutions to use (the one leaning toward bias).
 */
export const ik = (a: Vec, target: Vec, l1: number, l2: number, bias: Vec) => {
  const dx = target.x - a.x;
  const dy = target.y - a.y;
  const d = Math.hypot(dx, dy);
  const maxD = l1 + l2 - 0.01;
  const minD = Math.abs(l1 - l2) + 0.5;
  const dc = clamp(d || minD, minD, maxD);
  const ux = d ? dx / d : 0;
  const uy = d ? dy / d : 1;
  const end = { x: a.x + ux * dc, y: a.y + uy * dc };
  const base = Math.atan2(uy, ux);
  const cosA = (l1 * l1 + dc * dc - l2 * l2) / (2 * l1 * dc);
  const off = Math.acos(clamp(cosA, -1, 1));
  const e1 = { x: a.x + l1 * Math.cos(base + off), y: a.y + l1 * Math.sin(base + off) };
  const e2 = { x: a.x + l1 * Math.cos(base - off), y: a.y + l1 * Math.sin(base - off) };
  const mid = { x: (a.x + end.x) / 2, y: (a.y + end.y) / 2 };
  const s1 = (e1.x - mid.x) * bias.x + (e1.y - mid.y) * bias.y;
  const s2 = (e2.x - mid.x) * bias.x + (e2.y - mid.y) * bias.y;
  return { mid: s1 >= s2 ? e1 : e2, end };
};

/** Deterministic pseudo random in [0,1) */
export const rand = (seed: number) => {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/** Natural blink curve: returns lid multiplier (1 = open, 0 = shut). */
export const blinkAt = (t: number, seed = 1) => {
  const period = 3.4;
  const cycle = Math.floor(t / period);
  const offset = rand(cycle + seed) * 1.6;
  const local = t - cycle * period - offset;
  const dur = 0.16;
  if (local < 0 || local > dur) return 1;
  const k = local / dur;
  return Math.abs(Math.cos(k * Math.PI)); // 1 -> 0 -> 1
};

/** Sharp 4-point sparkle path centred at 0,0 */
export const sparklePath = (r: number, inner = 0.28) => {
  const i = r * inner;
  return `M0 ${-r} Q${i} ${-i} ${r} 0 Q${i} ${i} 0 ${r} Q${-i} ${i} ${-r} 0 Q${-i} ${-i} 0 ${-r}Z`;
};
