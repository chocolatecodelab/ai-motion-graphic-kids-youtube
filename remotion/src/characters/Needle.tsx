// Needle v0: a tiny holographic spark that lives in the Discovery Compass.
// Drawn in a 120x120 box, centred; the anchor (feet) is the bottom centre of the box.
import React from "react";
import { C } from "../brand";
import type { PuppetProps } from "./Kai";

export const Needle: React.FC<PuppetProps> = ({ pose, expression, action, mouth, blink, t, talking }) => {
  const glow = pose === "glow" ? 1.35 : 1 + Math.sin(t / 6) * 0.08;
  const spin = pose === "spin" ? (t * 12) % 360 : action === "loop_the_loop" ? (t * 18) % 360 : 0;
  const flash = action === "flash" ? Math.max(0, Math.sin(t / 2)) : 0;
  const dim = action === "dim" ? 0.55 : 1;
  const wiggle = action === "wiggle" ? Math.sin(t / 2) * 8 : 0;
  const e = expression;
  const eyeOpen = blink ? 0.15 : e === "surprised" ? 1.3 : e === "delighted" ? 0.5 : 1;
  const open = Math.max(mouth, e === "surprised" ? 0.5 : 0);
  const peek = pose === "peek" ? 0.4 : 0;

  return (
    <svg viewBox="0 0 120 120" width="100%" height="100%" style={{ overflow: "visible", opacity: dim }}>
      <defs>
        <radialGradient id="needleGlow">
          <stop offset="0%" stopColor="#FFF6C9" stopOpacity={1} />
          <stop offset="45%" stopColor={C.yellow} stopOpacity={0.7} />
          <stop offset="100%" stopColor={C.yellow} stopOpacity={0} />
        </radialGradient>
      </defs>
      <g transform={`translate(60 60) rotate(${spin + wiggle}) translate(-60 -60)`}>
        <circle cx={60} cy={60} r={58 * glow + flash * 20} fill="url(#needleGlow)" />
        {/* sparkles orbiting */}
        {[0, 1, 2, 3].map((i) => {
          const a = t / 9 + (i * Math.PI) / 2;
          return (
            <path key={i} d="M0 -6 L1.6 -1.6 L6 0 L1.6 1.6 L0 6 L-1.6 1.6 L-6 0 L-1.6 -1.6 Z"
              fill={C.white} transform={`translate(${60 + Math.cos(a) * 44} ${60 + Math.sin(a) * 30}) scale(${0.8 + 0.3 * Math.sin(t / 5 + i)})`} />
          );
        })}
        {/* the spark: star-shaped core */}
        <path d="M60 22 L69 48 L96 52 L74 68 L80 96 L60 80 L40 96 L46 68 L24 52 L51 48 Z"
          fill={C.yellow} stroke="#FFF2B3" strokeWidth={3} strokeLinejoin="round" />
        <circle cx={60} cy={60} r={20} fill="#FFE27A" />
        {/* face */}
        <g transform={`translate(0 ${peek * 10})`}>
          {[52, 68].map((cx) => (
            <ellipse key={cx} cx={cx} cy={57} rx={4} ry={5.5 * eyeOpen} fill={C.ink} />
          ))}
          {open > 0.08 || talking ? (
            <ellipse cx={60} cy={68} rx={4 + open * 2} ry={1.5 + open * 5} fill="#7A3B12" />
          ) : (
            <path d={`M54 66 Q60 ${e === "puzzled" ? 66 : 71} 66 66`} stroke="#7A3B12" strokeWidth={2.5} fill="none" strokeLinecap="round" />
          )}
        </g>
      </g>
    </svg>
  );
};
