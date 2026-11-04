import React from "react";
import { C } from "./palette";
import { lerp, sparklePath, rand } from "./math";

/* ------------------------------------------------------------------ */
/*  LIPA — origami map-bird companion (rig.v1)                         */
/*  Folded from Arka's old expedition map. Glows when it finds a trail. */
/*  Local space: body centre (0,0), facing right, ~140 x 100 units.     */
/* ------------------------------------------------------------------ */

export type LipaPose = {
  x: number;
  y: number;
  rot: number; // body pitch, degrees
  flap: number; // 1 = wings up, 0 = edge-on, -1 = wings down
  squash: number;
  glow: number; // 0..1
};

export type LipaEyes = "dot" | "wide" | "happy" | "squint" | "closed";
export type LipaExpression = {
  eyeL: LipaEyes;
  eyeR: LipaEyes;
  brows: "none" | "angry" | "worried" | "raised";
  beak: number; // 0..1 open
  blush: number;
  extra: "none" | "sparkle" | "question" | "sweat" | "shock";
  lookX: number;
};

const LP = (o: Partial<LipaPose>): LipaPose => ({ x: 0, y: 0, rot: -4, flap: 0.6, squash: 0, glow: 0.8, ...o });

export const LIPA_POSES = {
  float: LP({}),
  flap: LP({ flap: 1, rot: -10, squash: -0.05, y: -6 }),
  glide: LP({ flap: 0.12, rot: 6 }),
  dive: LP({ flap: -0.55, rot: 30, glow: 1 }),
  perch: LP({ flap: -0.12, rot: 0, squash: 0.07, glow: 0.45 }),
  loop: LP({ flap: 0.75, rot: -140 }),
} satisfies Record<string, LipaPose>;
export type LipaPoseName = keyof typeof LIPA_POSES;
export const LIPA_POSE_NAMES = Object.keys(LIPA_POSES) as LipaPoseName[];

const LX = (o: Partial<LipaExpression>): LipaExpression => ({
  eyeL: "dot",
  eyeR: "dot",
  brows: "none",
  beak: 0,
  blush: 0.4,
  extra: "none",
  lookX: 0.3,
  ...o,
});

export const LIPA_EXPRESSIONS = {
  neutral: LX({}),
  curious: LX({ eyeL: "dot", eyeR: "wide", brows: "raised", lookX: 0.8 }),
  surprised: LX({ eyeL: "wide", eyeR: "wide", beak: 0.9, brows: "raised", extra: "shock", blush: 0.2 }),
  delighted: LX({ eyeL: "happy", eyeR: "happy", beak: 0.6, blush: 0.8, extra: "sparkle" }),
  puzzled: LX({ eyeL: "squint", eyeR: "dot", brows: "worried", extra: "question", lookX: -0.4 }),
  determined: LX({ eyeL: "dot", eyeR: "dot", brows: "angry", beak: 0.15, blush: 0.2, lookX: 1 }),
  worried: LX({ eyeL: "wide", eyeR: "wide", brows: "worried", extra: "sweat", lookX: -0.2 }),
  laughing: LX({ eyeL: "happy", eyeR: "happy", beak: 1, blush: 0.9 }),
} satisfies Record<string, LipaExpression>;
export type LipaExpressionName = keyof typeof LIPA_EXPRESSIONS;
export const LIPA_EXPRESSION_NAMES = Object.keys(LIPA_EXPRESSIONS) as LipaExpressionName[];

export const lerpLipa = (a: LipaPose, b: LipaPose, k: number): LipaPose => ({
  x: lerp(a.x, b.x, k),
  y: lerp(a.y, b.y, k),
  rot: lerp(a.rot, b.rot, k),
  flap: lerp(a.flap, b.flap, k),
  squash: lerp(a.squash, b.squash, k),
  glow: lerp(a.glow, b.glow, k),
});

const frac = (x: number) => x - Math.floor(x);
/**
 * One wingbeat, p in [0,1): a quick power downstroke (40%) and a slower recovery upstroke
 * (60%). Both halves are half-cosines, so velocity is zero at the top and bottom: no snapping.
 */
const beat = (p: number) =>
  p < 0.4 ? Math.cos((Math.PI * p) / 0.4) : -Math.cos((Math.PI * (p - 0.4)) / 0.6);

/** Flap value for a continuous flight loop (1 = up, -1 = down). */
export const flapAt = (t: number, rate = 2.4) => beat(frac(t * rate)) * 0.95;

/**
 * Full flight sample: root flap, a lagging wing-tip flap (the paper bends, overlapping action),
 * and a body bob — the body rises at the end of each downstroke and settles on the upstroke.
 */
export const flightAt = (t: number, rate = 2.4, strength = 1) => {
  const p = frac(t * rate);
  return {
    flap: beat(p) * 0.95 * strength,
    flapTip: beat(frac(p - 0.11)) * 0.95 * strength,
    bob: -2.6 * Math.sin(Math.PI * 2 * (p - 0.1)) * strength,
  };
};

/* ------------------------------ drawing ---------------------------- */

const SW = 2.8;
const ink = { stroke: C.ink, strokeWidth: SW, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };
const poly = (pts: number[][]) => "M" + pts.map((p) => p.join(" ")).join(" L") + "Z";

const BASE_Y = -11;

const minAbs = (v: number) => (Math.abs(v) < 0.06 ? (v < 0 ? -0.06 : 0.06) : v);

/**
 * Wing with a bendable tip: root points follow `flap`, the tip follows `tip` (a lagged flap),
 * and the mid-wing corner sits between them, so the paper flexes through each stroke.
 * Each point is folded about the shoulder line: y' = BASE_Y + (y - BASE_Y) * f.
 */
const Wing: React.FC<{ flap: number; tip?: number; back?: boolean; t: number; clipId: string }> = ({
  flap,
  tip,
  back,
  t,
  clipId,
}) => {
  const f = minAbs(flap);
  const ft = minAbs(tip ?? flap);
  const fw = minAbs(lerp(f, ft, 0.45));
  const fold = (x: number, y: number, k: number) => [x, BASE_Y + (y - BASE_Y) * k];
  const F1 = fold(-16, -10, f);
  const F2 = fold(18, -12, f);
  const M = fold(1, -11, f);
  const T = fold(-2, -98, ft);
  const W = fold(-52, -68, fw);
  const under = fw < 0;
  const light = back ? C.paperMid : under ? C.paperMid : C.paper;
  const mid = back ? C.paperDark : under ? C.paperDark : C.paperMid;
  const showMap = !back && !under && fw > 0.25;
  const outer = poly([F1, M, T, W]);
  return (
    <g>
      <path d={outer} fill={light} {...ink} />
      <path d={poly([M, F2, T])} fill={mid} {...ink} />
      {showMap && (
        <g clipPath={`url(#${clipId})`}>
          <clipPath id={clipId}>
            <path d={outer} />
          </clipPath>
          <g
            opacity={Math.min(1, (fw - 0.25) * 3)}
            transform={`translate(0 ${BASE_Y}) scale(1 ${fw.toFixed(3)}) translate(0 ${-BASE_Y})`}
          >
            <path d="M-44 -64 C-36 -52 -24 -56 -20 -44 S-10 -28 -6 -20" fill="none" stroke={C.water} strokeWidth={2.4} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            <path d="M-30 -78 C-24 -66 -14 -70 -8 -58" fill="none" stroke={C.route} strokeWidth={1.8} strokeDasharray="2.5 3" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            <g transform={`translate(-24 -36) rotate(${(Math.sin(t * 2) * 10).toFixed(2)})`}>
              <path d={sparklePath(7, 0.26)} fill={C.brass} stroke={C.ink} strokeWidth={1.2} strokeLinejoin="round" />
              <circle r={1.4} fill={C.hat} />
            </g>
          </g>
        </g>
      )}
      <path d={`M${M[0]} ${M[1]} L${T[0]} ${T[1]}`} stroke={C.paperLine} strokeWidth={1.4} />
    </g>
  );
};

const Eye: React.FC<{ x: number; y: number; kind: LipaEyes; r: number; look: number }> = ({ x, y, kind, r, look }) => {
  switch (kind) {
    case "happy":
      return <path d={`M${x - r * 1.1} ${y + 1.5} Q${x} ${y - r * 1.6} ${x + r * 1.1} ${y + 1.5}`} fill="none" stroke={C.ink} strokeWidth={2.8} strokeLinecap="round" />;
    case "closed":
      return <path d={`M${x - r} ${y - 1} Q${x} ${y + r} ${x + r} ${y - 1}`} fill="none" stroke={C.ink} strokeWidth={2.6} strokeLinecap="round" />;
    case "squint":
      return <path d={`M${x - r} ${y} L${x + r} ${y - 1}`} fill="none" stroke={C.ink} strokeWidth={2.8} strokeLinecap="round" />;
    case "wide":
      return (
        <g>
          <circle cx={x} cy={y} r={r * 1.45} fill="#fff" stroke={C.ink} strokeWidth={2} />
          <circle cx={x + look * 1.2} cy={y} r={r * 0.7} fill={C.ink} />
          <circle cx={x + look * 1.2 - 1} cy={y - 1.2} r={0.9} fill="#fff" />
        </g>
      );
    default:
      return (
        <g>
          <ellipse cx={x + look} cy={y} rx={r * 0.85} ry={r * 1.1} fill={C.ink} />
          <circle cx={x + look - r * 0.3} cy={y - r * 0.45} r={r * 0.38} fill="#fff" />
        </g>
      );
  }
};

export type LipaProps = {
  pose: LipaPose;
  expression: LipaExpression;
  t?: number;
  uid?: string;
  facing?: 1 | -1;
  trail?: boolean;
  /** Lagged wing-tip flap (see flightAt); defaults to pose.flap (rigid wing). */
  flapTip?: number;
  /** Extra vertical body offset from wingbeats (see flightAt). */
  bob?: number;
};

export const Lipa: React.FC<LipaProps> = ({
  pose,
  expression: e,
  t = 0,
  uid = "lipa",
  facing = 1,
  trail = true,
  flapTip,
  bob = 0,
}) => {
  const sx = 1 + pose.squash * 0.7;
  const sy = 1 - pose.squash;
  const beakA = e.beak * 24;
  const hover = Math.sin(t * 3.2) * 2;
  const tip = flapTip ?? pose.flap;
  return (
    <g transform={`translate(${pose.x.toFixed(2)} ${(pose.y + hover + bob).toFixed(2)}) scale(${facing} 1)`}>
      <defs>
        <radialGradient id={`${uid}-glow`}>
          <stop offset="0" stopColor={C.glow} stopOpacity={0.85} />
          <stop offset="0.45" stopColor={C.glow} stopOpacity={0.32} />
          <stop offset="1" stopColor={C.glow} stopOpacity={0} />
        </radialGradient>
      </defs>
      <circle cx={6} cy={-18} r={92} fill={`url(#${uid}-glow)`} opacity={pose.glow} />
      {trail &&
        [0, 1, 2, 3, 4].map((i) => {
          const k = ((t * 0.9 + i / 5) % 1 + 1) % 1;
          const sz = (1 - k) * (4 + rand(i) * 4);
          return (
            <path
              key={i}
              d={sparklePath(sz)}
              transform={`translate(${(-70 - k * 70).toFixed(1)} ${(-6 + Math.sin(k * 7 + i) * 14 + (rand(i + 3) - 0.5) * 20).toFixed(1)})`}
              fill={C.glow}
              opacity={(1 - k) * pose.glow}
            />
          );
        })}
      <g transform={`rotate(${pose.rot.toFixed(2)}) scale(${sx.toFixed(4)} ${sy.toFixed(4)})`}>
        {/* back wing */}
        <g transform="translate(9 -3)">
          <Wing flap={pose.flap * 0.92} tip={tip * 0.92} back t={t} clipId={`${uid}-wb`} />
        </g>
        {/* tail */}
        <path d={poly([[-28, -4], [-76, -30], [-54, -2]])} fill={C.paper} {...ink} />
        <path d={poly([[-28, -4], [-54, -2], [-72, 16], [-24, 8]])} fill={C.paperMid} {...ink} />
        {/* body */}
        <path d={poly([[-32, -2], [-2, -20], [30, -12]])} fill={C.paper} {...ink} />
        <path d={poly([[-32, -2], [30, -12], [12, 16], [-20, 12]])} fill={C.paperMid} {...ink} />
        <path d="M-20 4 L8 0" stroke={C.paperLine} strokeWidth={1.3} strokeDasharray="2 3" />
        {/* head */}
        <g transform="translate(30 -12) scale(1.3) translate(-30 12)">
        <path d={poly([[22, -10], [30, -42], [50, -48], [62, -30], [52, -6]])} fill={C.paper} {...ink} />
        <path d={poly([[30, -42], [50, -48], [62, -30], [42, -32]])} fill="#FBF0D6" stroke={C.paperLine} strokeWidth={1.2} strokeLinejoin="round" />
        <path d={poly([[22, -10], [30, -42], [50, -48], [62, -30], [52, -6]])} fill="none" {...ink} />
        {/* beak */}
        <g transform={`rotate(${(-beakA * 0.35).toFixed(2)} 60 -26)`}>
          <path d={poly([[59, -34], [75, -28], [60, -25]])} fill={C.brass} {...ink} strokeWidth={2.2} />
        </g>
        <g transform={`rotate(${beakA.toFixed(2)} 60 -25)`}>
          <path d={poly([[60, -25], [72, -24], [58, -19]])} fill={C.brassDark} {...ink} strokeWidth={2.2} />
        </g>
        {/* face */}
        <ellipse cx={38} cy={-17} rx={4.2} ry={2.4} fill={C.blush} opacity={e.blush} />
        <ellipse cx={55} cy={-17} rx={3.2} ry={2.2} fill={C.blush} opacity={e.blush} />
        <Eye x={40} y={-27} kind={e.eyeL} r={4.4} look={e.lookX} />
        <Eye x={53} y={-28} kind={e.eyeR} r={3.8} look={e.lookX} />
        {e.brows !== "none" && (
          <g stroke={C.ink} strokeWidth={2.4} strokeLinecap="round">
            {e.brows === "angry" && <path d="M35 -37 L44 -34 M49 -35 L57 -38" />}
            {e.brows === "worried" && <path d="M35 -34 L44 -38 M49 -38 L57 -35" />}
            {e.brows === "raised" && <path d="M35 -38 Q40 -41 45 -38 M49 -39 Q53 -42 57 -39" fill="none" />}
          </g>
        )}
        </g>
        {/* front wing */}
        <Wing flap={pose.flap} tip={tip} t={t} clipId={`${uid}-wf`} />
      </g>
      {e.extra === "sparkle" && (
        <g>
          <path d={sparklePath(8 + Math.sin(t * 6) * 2)} transform="translate(72 -60)" fill={C.glow} stroke={C.ink} strokeWidth={1.6} strokeLinejoin="round" />
          <path d={sparklePath(5)} transform="translate(84 -40)" fill={C.glow} stroke={C.ink} strokeWidth={1.4} strokeLinejoin="round" />
        </g>
      )}
      {e.extra === "question" && (
        <g transform={`translate(74 ${-62 + Math.sin(t * 4) * 2}) rotate(10) scale(0.72)`}>
          <path d="M-7 -8 Q-7 -18 2 -18 Q11 -18 11 -10 Q11 -4 3 0 L3 6" fill="none" stroke={C.ink} strokeWidth={8.5} strokeLinecap="round" strokeLinejoin="round" />
          <path d="M-7 -8 Q-7 -18 2 -18 Q11 -18 11 -10 Q11 -4 3 0 L3 6" fill="none" stroke={C.glow} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
          <circle cx={3} cy={15} r={4.4} fill={C.glow} stroke={C.ink} strokeWidth={2.2} />
        </g>
      )}
      {e.extra === "sweat" && (
        <path d="M0 -8 Q6 2 0 5 Q-6 2 0 -8Z" transform={`translate(68 ${-46 + ((t * 10) % 5)})`} fill="#8CC8F0" stroke={C.ink} strokeWidth={2} strokeLinejoin="round" />
      )}
      {e.extra === "shock" && (
        <g stroke={C.glow} strokeWidth={3.2} strokeLinecap="round">
          <path d="M66 -58 L74 -70 M76 -46 L90 -50 M50 -62 L52 -76" />
        </g>
      )}
    </g>
  );
};
