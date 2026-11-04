// Kai v0: placeholder vector puppet (rig.v0). Final design comes from the M2 Character Bible.
// Drawn facing camera in a 200x400 box; feet at the bottom centre.
import React from "react";
import { C } from "../brand";

export interface PuppetProps {
  pose: string;
  expression: string;
  action: string | null;
  mouth: number; // 0..1 openness (from voice amplitude)
  blink: boolean;
  t: number; // frames since the shot started (for actions / cycles)
  walkPhase: number;
  talking: boolean;
}

// Arm "raise" angles (0 = hanging, 90 = horizontal out, 180 = straight up) and elbow bend.
type Arm = [raise: number, bend: number];
const POSES: Record<string, { l: Arm; r: Arm; lean: number; crouch: number; headTilt: number }> = {
  idle: { l: [12, 8], r: [12, 8], lean: 0, crouch: 0, headTilt: 0 },
  talk: { l: [14, 10], r: [55, 70], lean: 0, crouch: 0, headTilt: 3 },
  point: { l: [12, 8], r: [95, 0], lean: 3, crouch: 0, headTilt: 0 },
  think: { l: [20, 100], r: [40, 140], lean: -2, crouch: 0, headTilt: -8 },
  surprised: { l: [125, 30], r: [125, 30], lean: -3, crouch: 0, headTilt: 0 },
  celebrate: { l: [160, 10], r: [160, 10], lean: 0, crouch: 0, headTilt: 4 },
  walk: { l: [18, 12], r: [18, 12], lean: 4, crouch: 0, headTilt: 0 },
  hold_compass: { l: [35, 95], r: [35, 95], lean: 0, crouch: 0, headTilt: 6 },
  crouch: { l: [40, 60], r: [40, 60], lean: 6, crouch: 1, headTilt: 0 },
  look_up: { l: [15, 10], r: [15, 10], lean: -4, crouch: 0, headTilt: -14 },
};

const ACTIONS = (action: string | null, t: number) => {
  const wave = Math.sin(t / 3);
  switch (action) {
    case "wave": return { r: [150 + wave * 12, 30 + wave * 25] as Arm };
    case "nod": return { headY: Math.max(0, Math.sin(t / 4)) * 6 };
    case "gasp": return { headY: -4, mouthO: true };
    case "look_around": return { headX: Math.sin(t / 10) * 8 };
    case "tap_compass": return { r: [40, 100 + Math.max(0, Math.sin(t / 3)) * 20] as Arm };
    case "shrug": return { l: [60, 120] as Arm, r: [60, 120] as Arm, shoulders: -8 };
    case "scratch_head": return { r: [165, 150 + wave * 8] as Arm };
    case "jump": return {};
    default: return {};
  }
};

const ArmShape: React.FC<{ side: "l" | "r"; arm: Arm; walk: number }> = ({ side, arm, walk }) => {
  const dir = side === "l" ? 1 : -1;
  const [raise, bend] = arm;
  const swing = walk ? Math.sin(walk * Math.PI * 2) * 14 * dir : 0;
  const sx = side === "l" ? 62 : 138;
  return (
    <g transform={`rotate(${dir * raise + swing} ${sx} 168)`}>
      {/* upper arm: hoodie sleeve */}
      <rect x={sx - 13} y={162} width={26} height={62} rx={13} fill={C.teal} />
      <g transform={`rotate(${-dir * bend} ${sx} 218)`}>
        {/* rolled sleeve cuff + forearm + hand */}
        <rect x={sx - 14} y={210} width={28} height={14} rx={7} fill="#3E9C88" />
        <rect x={sx - 10} y={220} width={20} height={44} rx={10} fill={C.skin} />
        <circle cx={sx} cy={268} r={13} fill={C.skin} />
      </g>
    </g>
  );
};

const Face: React.FC<{ expression: string; mouth: number; blink: boolean; o: boolean }> = ({
  expression, mouth, blink, o,
}) => {
  const e = expression;
  const eyeOpen = blink ? 0.12 : e === "surprised" ? 1.25 : e === "delighted" ? 0.55 : e === "puzzled" ? 0.75 : 1;
  const browL = { neutral: 0, curious: -6, surprised: -10, delighted: -4, puzzled: 4, determined: 7 }[e] ?? 0;
  const browR = { neutral: 0, curious: 2, surprised: -10, delighted: -4, puzzled: -6, determined: 7 }[e] ?? 0;
  const smile = { neutral: 2, curious: 4, surprised: 0, delighted: 10, puzzled: -2, determined: 4 }[e] ?? 2;
  const open = Math.max(o ? 0.8 : 0, mouth);
  return (
    <g>
      {/* eyes */}
      {[80, 120].map((cx, i) => (
        <g key={cx}>
          <ellipse cx={cx} cy={98} rx={11} ry={13 * eyeOpen} fill={C.white} />
          {eyeOpen > 0.3 && <circle cx={cx + (e === "curious" ? 2 : 0)} cy={99} r={6.5} fill={C.ink} />}
          {eyeOpen > 0.3 && <circle cx={cx + 2.5} cy={96} r={2} fill={C.white} />}
          <path d={`M${cx - 12} ${80 + (i ? browR : browL)} Q${cx} ${74 + (i ? browR : browL)} ${cx + 12} ${80 + (i ? browR : browL) * 0.4}`}
            stroke={C.hair} strokeWidth={4} fill="none" strokeLinecap="round" />
        </g>
      ))}
      {/* cheeks */}
      <circle cx={70} cy={118} r={7} fill="#E6876B" opacity={0.45} />
      <circle cx={130} cy={118} r={7} fill="#E6876B" opacity={0.45} />
      {/* mouth: smile curve + opening driven by voice amplitude */}
      {open > 0.08 ? (
        <ellipse cx={100} cy={124 + smile * 0.2} rx={10 + open * 4} ry={3 + open * 10} fill="#5A2230" />
      ) : (
        <path d={`M88 ${122} Q100 ${122 + smile} 112 ${122}`} stroke="#5A2230" strokeWidth={4} fill="none" strokeLinecap="round" />
      )}
    </g>
  );
};

export const Kai: React.FC<PuppetProps> = ({ pose, expression, action, mouth, blink, t, walkPhase, talking }) => {
  const base = POSES[pose] ?? POSES.idle;
  const act = ACTIONS(action, t) as { l?: Arm; r?: Arm; headX?: number; headY?: number; mouthO?: boolean; shoulders?: number };
  let r: Arm = act.r ?? base.r;
  const l: Arm = act.l ?? base.l;
  if (pose === "talk" && talking) r = [r[0] + Math.sin(t / 5) * 8, r[1] + Math.sin(t / 4) * 10];
  const crouch = base.crouch * 30;
  const headX = (act.headX ?? 0) + (talking ? Math.sin(t / 6) * 1.5 : 0);
  const headY = (act.headY ?? 0) + crouch + (act.shoulders ?? 0) * 0.3 + (talking ? Math.abs(Math.sin(t / 5)) * 2 : 0);
  const step = walkPhase ? Math.sin(walkPhase * Math.PI * 2) * 14 : 0;

  return (
    <svg viewBox="0 0 200 400" width="100%" height="100%" style={{ overflow: "visible" }}>
      <g transform={`rotate(${base.lean} 100 400)`}>
        {/* legs: skin below blue shorts, band-aid on the left knee, orange sneakers */}
        {[[82, -step], [118, step]].map(([x, s], i) => (
          <g key={i} transform={`rotate(${s} ${x} 290)`}>
            <rect x={x - 10} y={290 + crouch * 0.5} width={20} height={86 - crouch} rx={9} fill={C.skin} />
            {i === 0 && <rect x={x - 11} y={322} width={22} height={9} rx={3} fill="#F3D9B0" transform={`rotate(-12 ${x} 326)`} />}
            <path d={`M${x - 16} ${388} Q${x - 16} ${370} ${x} ${370} L${x + 18} ${376} Q${x + 24} ${388} ${x + 12} ${392} L${x - 14} ${392} Z`}
              fill={C.orange} />
            <rect x={x - 16} y={388} width={34} height={6} rx={3} fill={C.cream} />
          </g>
        ))}
        <path d={`M62 ${262 + crouch * 0.6} L138 ${262 + crouch * 0.6} L142 ${306} L104 ${306} L100 ${292} L96 ${306} L58 ${306} Z`} fill={C.blue} />
        {/* arms behind/in front of torso */}
        <ArmShape side="l" arm={l} walk={walkPhase} />
        {/* torso: oversized teal hoodie with pocket + utility belt */}
        <g transform={`translate(0 ${crouch * 0.6})`}>
          <path d="M60 164 Q100 146 140 164 L146 268 Q100 280 54 268 Z" fill={C.teal} />
          <path d="M74 220 Q100 214 126 220 L122 250 Q100 254 78 250 Z" fill="#3E9C88" />
          <rect x={56} y={256} width={88} height={12} rx={5} fill="#7A4E2D" />
          <rect x={70} y={252} width={10} height={20} rx={2} fill={C.brass} />
          <rect x={120} y={252} width={8} height={22} rx={2} fill="#9AA5B1" />
          <path d="M84 160 Q100 176 116 160" stroke="#3E9C88" strokeWidth={6} fill="none" />
        </g>
        <ArmShape side="r" arm={r} walk={walkPhase ? (walkPhase + 0.5) % 1 : 0} />
        {pose === "hold_compass" && (
          <g transform={`translate(100 ${236 + crouch * 0.6})`}>
            <circle r={20} fill={C.brass} stroke="#8C6A22" strokeWidth={4} />
            <circle r={13} fill={C.cream} />
            <path d={`M0 -10 L4 0 L0 10 L-4 0 Z`} fill={C.orange} transform={`rotate(${Math.sin(t / 8) * 25})`} />
          </g>
        )}
        {/* head */}
        <g transform={`translate(${headX} ${headY}) rotate(${base.headTilt} 100 150)`}>
          <rect x={90} y={138} width={20} height={20} fill={C.skinShade} />
          <circle cx={58} cy={104} r={11} fill={C.skin} />
          <circle cx={142} cy={104} r={11} fill={C.skin} />
          <ellipse cx={100} cy={100} rx={46} ry={50} fill={C.skin} />
          {/* short hair with a tuft */}
          <path d="M54 92 Q52 48 100 46 Q148 48 146 92 Q132 70 112 72 Q98 60 84 72 Q66 70 54 92 Z" fill={C.hair} />
          <path d="M98 50 Q104 30 118 36 Q106 40 108 52 Z" fill={C.hair} />
          <Face expression={expression} mouth={mouth} blink={blink} o={Boolean(act.mouthO)} />
        </g>
      </g>
    </svg>
  );
};
