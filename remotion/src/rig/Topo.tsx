import React from "react";
import { rand } from "./math";

/** Topographic contour lines — the expedition backdrop used on the board and in video. */
export const topoPaths = (w: number, h: number, seed = 3, rings = 9, phase = 0) => {
  const centers = [
    { x: w * 0.18, y: h * 0.32 },
    { x: w * 0.78, y: h * 0.7 },
    { x: w * 0.62, y: h * 0.08 },
  ];
  const paths: string[] = [];
  centers.forEach((c, ci) => {
    for (let k = 1; k <= rings; k++) {
      const r0 = k * Math.max(w, h) * 0.045;
      const s1 = rand(seed + ci * 13 + k) * 6;
      const s2 = rand(seed + ci * 7 + k * 3) * 6;
      const pts: string[] = [];
      const N = 72;
      for (let i = 0; i <= N; i++) {
        const a = (i / N) * Math.PI * 2;
        const r = r0 * (1 + 0.13 * Math.sin(3 * a + s1 + phase) + 0.07 * Math.sin(5 * a + s2 - phase * 0.6));
        pts.push(`${(c.x + Math.cos(a) * r * 1.25).toFixed(1)} ${(c.y + Math.sin(a) * r).toFixed(1)}`);
      }
      paths.push("M" + pts.join(" L") + "Z");
    }
  });
  return paths;
};

export const Topo: React.FC<{ w: number; h: number; color: string; seed?: number; phase?: number; strokeWidth?: number; opacity?: number }> = ({
  w,
  h,
  color,
  seed = 3,
  phase = 0,
  strokeWidth = 2,
  opacity = 1,
}) => (
  <g opacity={opacity}>
    {topoPaths(w, h, seed, 9, phase).map((d, i) => (
      <path key={i} d={d} fill="none" stroke={color} strokeWidth={i % 3 === 0 ? strokeWidth * 1.6 : strokeWidth} />
    ))}
  </g>
);
