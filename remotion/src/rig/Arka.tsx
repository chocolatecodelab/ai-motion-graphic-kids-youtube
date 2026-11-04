import React from "react";
import { C } from "./palette";
import { Vec, clamp, deg, ik, rotateAround, sparklePath } from "./math";
import type {
  ArkaExpression,
  ArkaPose,
  Brow,
  EyeState,
  HandShape,
  MouthKind,
} from "./arkaData";

/* ------------------------------------------------------------------ */
/*  ARKA — production rig (rig.v1)                                     */
/*  Pure SVG <g>. No Remotion imports so it renders anywhere           */
/*  (Remotion, react-dom/server, browser).                              */
/* ------------------------------------------------------------------ */

const HIP_Y = -104;
const HIP_X = 17;
const THIGH = 47;
const SHIN = 46;
const SHOULDER_Y = -98;
const SHOULDER_X = 40;
const UPPER_ARM = 41;
const FOREARM = 39;
const NECK_Y = -108;
export const HEAD_SCALE = 1.08;
const ARM_W = 17;
const LEG_W = 21;
const OUT = 4.6; // total outline thickness added to stroked limbs
const SW = 3.2; // outline width for filled shapes

const ink = { stroke: C.ink, strokeWidth: SW, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

export type ArkaProps = {
  pose: ArkaPose;
  expression: ArkaExpression;
  /** seconds — drives scarf, breathing, compass needle, sparkles */
  t?: number;
  /** extra lid multiplier (1 = open, 0 = closed) for blinks */
  blink?: number;
  facing?: 1 | -1;
  shadow?: boolean;
  /** unique id prefix when many rigs share one SVG document */
  uid?: string;
  breathe?: boolean;
  /** Follow-through (polish): head trails the body. Derive from pose velocity, e.g.
   *  y = (rootY_now - rootY_2framesAgo) * 0.6, tilt = (lean_3framesAgo - lean_now) * 0.7. */
  overlap?: { y: number; tilt: number };
};

/* ------------------------------ helpers ---------------------------- */

const Stroked: React.FC<{ d: string; w: number; color: string; cap?: "round" | "butt" }> = ({
  d,
  w,
  color,
  cap = "round",
}) => (
  <>
    <path d={d} fill="none" stroke={C.ink} strokeWidth={w + OUT} strokeLinecap={cap} strokeLinejoin="round" />
    <path d={d} fill="none" stroke={color} strokeWidth={w} strokeLinecap={cap} strokeLinejoin="round" />
  </>
);

const along = (a: Vec, b: Vec, k: number): Vec => ({ x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k });
const P = (v: Vec) => `${v.x.toFixed(2)} ${v.y.toFixed(2)}`;

/** Polish (owner request): limb path with straight bones and a rounded joint (fillet)
 *  instead of a hard kink, so elbows and knees bend smoothly through every pose blend. */
const FILLET = 0.42;
const limbPath = (l: { a: Vec; mid: Vec; end: Vec }) => {
  const p1 = along(l.mid, l.a, FILLET);
  const p2 = along(l.mid, l.end, FILLET);
  return `M${P(l.a)} L${P(p1)} Q${P(l.mid)} ${P(p2)} L${P(l.end)}`;
};

/* ------------------------------- hands ----------------------------- */

const Hand: React.FC<{ at: Vec; angle: number; shape: HandShape; mirror: boolean }> = ({ at, angle, shape, mirror }) => {
  const finger = (d: string, w = 6.5) => <Stroked d={d} w={w} color={C.skin} />;
  return (
    <g transform={`translate(${P(at)}) rotate(${angle.toFixed(2)}) scale(${mirror ? -1 : 1} 1)`}>
      {shape === "open" && (
        <>
          {finger("M-6 10 L-8 22")}
          {finger("M0 11 L0 24")}
          {finger("M6 10 L8 21")}
          {finger("M9 3 L17 9", 7)}
          <ellipse cx={0} cy={5} rx={11} ry={11.5} fill={C.skin} {...ink} />
          <path d="M-6 10 L-7.5 20 M0 11 L0 22 M6 10 L7.5 19" stroke={C.skin} strokeWidth={6.5} strokeLinecap="round" />
          <path d="M8.5 3.5 L15 8.5" stroke={C.skin} strokeWidth={7} strokeLinecap="round" />
        </>
      )}
      {shape === "point" && (
        <>
          {finger("M-2 10 L-2 30", 7)}
          <circle cx={0} cy={5} r={11.5} fill={C.skin} {...ink} />
          <path d="M-2 10 L-2 28" stroke={C.skin} strokeWidth={7} strokeLinecap="round" />
          <ellipse cx={8} cy={2} rx={4.6} ry={7} transform="rotate(-18 8 2)" fill={C.skin} {...ink} strokeWidth={2.4} />
        </>
      )}
      {(shape === "fist" || shape === "grip") && (
        <>
          <circle cx={0} cy={5} r={11.5} fill={C.skin} {...ink} />
          <path d="M-7 10 Q-4 13 -1 10.5 M-1 11 Q2 14 5 11" fill="none" stroke={C.skinShade} strokeWidth={2.2} strokeLinecap="round" />
          <ellipse cx={8.5} cy={1.5} rx={4.6} ry={7} transform="rotate(-18 8.5 1.5)" fill={C.skin} {...ink} strokeWidth={2.4} />
        </>
      )}
    </g>
  );
};

/* ------------------------------- arms ------------------------------ */

type Limb = { a: Vec; mid: Vec; end: Vec };
const solveArm = (side: "L" | "R", target: Vec): Limb => {
  const a = { x: side === "L" ? -SHOULDER_X : SHOULDER_X, y: SHOULDER_Y };
  const r = ik(a, target, UPPER_ARM, FOREARM, side === "L" ? { x: -0.5, y: 0.85 } : { x: 0.5, y: 0.85 });
  return { a, mid: r.mid, end: r.end };
};
const solveLeg = (side: "L" | "R", hipY: number, foot: Vec): Limb => {
  const a = { x: side === "L" ? -HIP_X : HIP_X, y: hipY };
  const r = ik(a, foot, THIGH, SHIN, side === "L" ? { x: -1, y: -0.15 } : { x: 1, y: -0.15 });
  return { a, mid: r.mid, end: r.end };
};

const ArmShape: React.FC<{ l: Limb; cuff: boolean }> = ({ l, cuff }) => {
  const d = limbPath(l);
  const sl = along(l.a, l.mid, 0.6);
  const c1 = along(l.mid, l.end, 0.66);
  const c2 = along(l.mid, l.end, 0.86);
  return (
    <g>
      <Stroked d={d} w={ARM_W} color={C.skin} />
      {cuff && (
        <>
          <Stroked d={`M${P(c1)} L${P(c2)}`} w={ARM_W + 3} color={C.band} cap="butt" />
          <circle cx={(c1.x + c2.x) / 2} cy={(c1.y + c2.y) / 2} r={2.6} fill={C.brass} stroke={C.ink} strokeWidth={1.4} />
        </>
      )}
      <Stroked d={`M${P(l.a)} L${P(sl)}`} w={27} color={C.shirt} />
      <path
        d={`M${P(along(l.a, l.mid, 0.12))} L${P(sl)}`}
        stroke={C.shirtShade}
        strokeWidth={7}
        strokeLinecap="round"
        opacity={0.8}
        transform="translate(3 2)"
      />
    </g>
  );
};

/* -------------------------------- legs ----------------------------- */

const Shoe: React.FC<{ at: Vec; mirror: boolean; lift: number }> = ({ at, mirror, lift }) => (
  <g transform={`translate(${P(at)}) rotate(${(mirror ? -1 : 1) * lift * 12}) scale(${mirror ? -1 : 1} 1)`}>
    <path d="M-15 -4 Q-17 11 -5 12 L13 12 Q23 12 21 3 Q18 -7 5 -9 Q-11 -11 -15 -4Z" fill={C.shoe} {...ink} />
    <path d="M-16 6 Q-14 13 -4 13 L13 13 Q22 13 22 6" fill="none" stroke={C.sole} strokeWidth={4.5} strokeLinecap="round" />
    <path d="M-17 5 Q-15 15 -4 15 L13 15 Q24 15 23 5" fill="none" stroke={C.ink} strokeWidth={2.4} strokeLinecap="round" />
    <path d="M-3 -6 L4 -1 M2 -8 L9 -3" stroke={C.sole} strokeWidth={2.4} strokeLinecap="round" />
    <path d="M8 -1 Q16 0 18 6" fill="none" stroke={C.shoeDark} strokeWidth={3} strokeLinecap="round" opacity={0.7} />
  </g>
);

const LegShape: React.FC<{ l: Limb }> = ({ l }) => {
  const d = limbPath(l);
  const s1 = along(l.mid, l.end, 0.62);
  const tube = along(l.a, l.mid, 0.55);
  return (
    <g>
      <Stroked d={d} w={LEG_W} color={C.skin} />
      {/* sock */}
      <Stroked d={`M${P(s1)} L${P(l.end)}`} w={LEG_W + 2} color={C.sock} cap="butt" />
      <path d={`M${P(along(l.mid, l.end, 0.7))} L${P(along(l.mid, l.end, 0.76))}`} stroke={C.scarf} strokeWidth={LEG_W + 2} />
      {/* shorts leg */}
      <Stroked d={`M${P(l.a)} L${P(tube)}`} w={33} color={C.shorts} cap="butt" />
      <path d={`M${P(along(l.a, l.mid, 0.4))} L${P(tube)}`} stroke={C.shortsShade} strokeWidth={33} />
    </g>
  );
};

/* ------------------------------- scarf ----------------------------- */

const scarfRibbon = (t: number, wind: number) => {
  const base = { x: -26, y: -104 };
  const w = clamp(wind, 0, 1.5);
  const ang = ((96 + 80 * Math.min(w, 1.1)) * Math.PI) / 180;
  const u = { x: Math.cos(ang), y: Math.sin(ang) };
  const n = { x: -u.y, y: u.x };
  const len = 64 + 52 * w;
  const amp = 3 + 7.5 * w;
  const N = 18;
  const left: Vec[] = [];
  const right: Vec[] = [];
  const center: Vec[] = [];
  for (let i = 0; i <= N; i++) {
    const s = i / N;
    const wave = Math.sin(s * 5.2 - t * 8.5) * amp * s + Math.sin(s * 9 - t * 13) * 1.6 * s * w;
    const droop = s * s * 14 * (1.2 - Math.min(w, 1.2));
    const c = {
      x: base.x + u.x * s * len + n.x * wave,
      y: base.y + u.y * s * len + n.y * wave + droop,
    };
    const half = 9 - 2.2 * s;
    center.push(c);
    left.push({ x: c.x + n.x * half, y: c.y + n.y * half });
    right.push({ x: c.x - n.x * half, y: c.y - n.y * half });
  }
  const d =
    `M${P(left[0])} ` +
    left.slice(1).map((p) => `L${P(p)}`).join(" ") +
    ` L${P(right[N])} ` +
    right
      .slice(0, N)
      .reverse()
      .map((p) => `L${P(p)}`)
      .join(" ") +
    " Z";
  return { d, center, left, right, u, n };
};

const Scarf: React.FC<{ t: number; wind: number }> = ({ t, wind }) => {
  const r = scarfRibbon(t, wind);
  const N = r.center.length - 1;
  const band = (k0: number, k1: number) => {
    const i0 = Math.round(k0 * N);
    const i1 = Math.round(k1 * N);
    const pts = [...r.left.slice(i0, i1 + 1), ...r.right.slice(i0, i1 + 1).reverse()];
    return "M" + pts.map(P).join(" L") + " Z";
  };
  const tip = r.center[N];
  const tipL = r.left[N];
  const tipR = r.right[N];
  const motif = r.center[Math.round(N * 0.82)];
  const motifAng = deg(Math.atan2(r.center[N].y - r.center[N - 2].y, r.center[N].x - r.center[N - 2].x));
  return (
    <g>
      <path d={r.d} fill={C.scarf} stroke={C.ink} strokeWidth={SW} strokeLinejoin="round" />
      <path d={band(0.0, 0.5)} fill={C.scarfDark} opacity={0.45} />
      <path d={band(0.62, 0.68)} fill={C.hat} />
      {/* kawung motif — a nod to Javanese batik */}
      <g transform={`translate(${P(motif)}) rotate(${motifAng.toFixed(1)})`}>
        {[0, 90, 180, 270].map((a) => (
          <ellipse key={a} cx={0} cy={-3.6} rx={2.2} ry={3.4} transform={`rotate(${a})`} fill={C.hat} />
        ))}
        <circle r={1.1} fill={C.scarfDark} />
      </g>
      {/* fringe */}
      {[0.15, 0.4, 0.65, 0.9].map((k) => {
        const s = { x: tipL.x + (tipR.x - tipL.x) * k, y: tipL.y + (tipR.y - tipL.y) * k };
        const dir = { x: tip.x - r.center[N - 1].x, y: tip.y - r.center[N - 1].y };
        const m = Math.hypot(dir.x, dir.y) || 1;
        const e = { x: s.x + (dir.x / m) * 7, y: s.y + (dir.y / m) * 7 };
        return <path key={k} d={`M${P(s)} L${P(e)}`} stroke={C.scarfDark} strokeWidth={2.4} strokeLinecap="round" />;
      })}
    </g>
  );
};

/* ------------------------------- face ------------------------------ */

const Eye: React.FC<{ cx: number; cy: number; e: EyeState; far: boolean; side: "L" | "R"; uid: string; blink: number; t: number }> = ({
  cx,
  cy,
  e,
  far,
  side,
  uid,
  blink,
  t,
}) => {
  const rx = 13.4 * (far ? 0.9 : 1);
  const ry = 16.4;
  const open = clamp(e.open * blink, 0, 1);
  const outer = side === "L" ? -1 : 1;
  if (e.shape === "happy") {
    return (
      <path
        d={`M${cx - rx} ${cy + 4} Q${cx} ${cy - ry + 1} ${cx + rx} ${cy + 4}`}
        fill="none"
        stroke={C.ink}
        strokeWidth={4.6}
        strokeLinecap="round"
      />
    );
  }
  if (e.shape === "closed" || open < 0.1) {
    return (
      <g>
        <path d={`M${cx - rx - 1} ${cy} Q${cx} ${cy + 7} ${cx + rx + 1} ${cy}`} fill="none" stroke={C.ink} strokeWidth={4.4} strokeLinecap="round" />
        <path d={`M${cx + outer * (rx + 1)} ${cy} l${outer * 4} -3`} stroke={C.ink} strokeWidth={3} strokeLinecap="round" />
      </g>
    );
  }
  const id = `${uid}-eye${side}`;
  const top = cy - ry;
  const lidY = top + (1 - open) * ry * 1.7;
  const ix = cx + e.lookX * 3.6;
  const iy = cy + e.lookY * 3.6 + 1.5;
  const ir = e.iris;
  const lowY = cy + ry - e.lower * ry * 0.9;
  return (
    <g>
      <defs>
        <clipPath id={id}>
          <ellipse cx={cx} cy={cy} rx={rx} ry={ry} />
        </clipPath>
        <linearGradient id={`${id}-g`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={C.irisDark} />
          <stop offset="0.55" stopColor={C.iris} />
          <stop offset="1" stopColor={C.irisLight} />
        </linearGradient>
      </defs>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill={C.sclera} />
      <g clipPath={`url(#${id})`}>
        {e.shape === "star" ? (
          <>
            <ellipse cx={ix} cy={iy} rx={10.5 * ir} ry={13 * ir} fill={`url(#${id}-g)`} />
            <path d={sparklePath(10 * ir, 0.3)} transform={`translate(${ix} ${iy}) rotate(${(Math.sin(t * 3) * 8).toFixed(2)})`} fill="#FFF6D6" />
            <circle cx={ix + 5} cy={iy - 6} r={2.2} fill="#fff" />
          </>
        ) : (
          <>
            <ellipse cx={ix} cy={iy} rx={9.6 * ir} ry={12.6 * ir} fill={`url(#${id}-g)`} />
            <ellipse cx={ix} cy={iy - 0.5} rx={4.6 * ir} ry={6.6 * ir} fill={C.pupil} />
            <ellipse cx={ix} cy={iy + 6 * ir} rx={6 * ir} ry={2.6 * ir} fill={C.irisLight} opacity={0.6} />
            <circle cx={ix - 3.6 * ir} cy={iy - 5 * ir} r={3.9 * ir} fill="#fff" />
            <circle cx={ix + 3.8 * ir} cy={iy + 4.6 * ir} r={1.8 * ir} fill="#fff" />
          </>
        )}
        <ellipse cx={cx} cy={top} rx={rx + 2} ry={6} fill="#D9CBDD" opacity={0.55} />
        {open < 1 && (
          <path
            d={`M${cx - rx - 3} ${top - 3} L${cx + rx + 3} ${top - 3} L${cx + rx + 3} ${lidY + 3} Q${cx} ${lidY - 5} ${cx - rx - 3} ${lidY + 4} Z`}
            fill={C.skin}
          />
        )}
        {e.lower > 0 && (
          <path d={`M${cx - rx - 3} ${cy + ry + 3} L${cx + rx + 3} ${cy + ry + 3} L${cx + rx + 3} ${lowY} Q${cx} ${lowY - 4} ${cx - rx - 3} ${lowY} Z`} fill={C.skin} />
        )}
      </g>
      {/* lash */}
      <path
        d={`M${cx - rx - 2} ${lidY + 4} Q${cx} ${lidY - 5.5} ${cx + rx + 2} ${lidY + 3.5}`}
        fill="none"
        stroke={C.ink}
        strokeWidth={4.8}
        strokeLinecap="round"
      />
      <path d={`M${cx + outer * (rx + 1.5)} ${lidY + 3.6} l${outer * 4.5} -3.2`} stroke={C.ink} strokeWidth={3.4} strokeLinecap="round" />
      <path d={`M${cx - rx * 0.55} ${lowY - 0.5} Q${cx} ${lowY + 2.2} ${cx + rx * 0.55} ${lowY - 0.5}`} fill="none" stroke={C.ink} strokeWidth={2} strokeLinecap="round" opacity={0.55} />
    </g>
  );
};

const BrowShape: React.FC<{ cx: number; cy: number; b: Brow; side: "L" | "R" }> = ({ cx, cy, b, side }) => {
  const rot = side === "L" ? b.rot : -b.rot;
  return (
    <path
      d="M-9 1.5 Q0 -3 9 0.5"
      transform={`translate(${cx} ${cy + b.y}) rotate(${rot})`}
      fill="none"
      stroke={C.brow}
      strokeWidth={4.6}
      strokeLinecap="round"
    />
  );
};

const Mouth: React.FC<{ kind: MouthKind; open: number }> = ({ kind, open }) => {
  const line = { fill: "none", stroke: C.ink, strokeWidth: 3.4, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const filled = { fill: C.mouth, stroke: C.ink, strokeWidth: 3, strokeLinejoin: "round" as const };
  switch (kind) {
    case "smile":
      return <path d="M-9 -2 Q0 6 9 -2" {...line} />;
    case "smirk":
      return <path d="M-8 1 Q2 4 10 -4" {...line} />;
    case "flat":
      return <path d="M-7 1 L7 1" {...line} />;
    case "wavy":
      return <path d="M-10 2 Q-5 -3 0 2 Q5 7 10 2" {...line} />;
    case "cat":
      return <path d="M-10 -2 Q-5 4 0 -1 Q5 4 10 -2" {...line} />;
    case "o":
      return (
        <g>
          <ellipse cx={0} cy={1} rx={4.6 + open * 1.6} ry={5.4 + open * 2} {...filled} />
          <ellipse cx={0} cy={4 + open} rx={2.6} ry={1.6} fill={C.tongue} />
        </g>
      );
    case "open":
      return (
        <g>
          <ellipse cx={0} cy={2} rx={8} ry={10.5} {...filled} />
          <ellipse cx={0} cy={7.5} rx={5} ry={3} fill={C.tongue} />
        </g>
      );
    case "grin":
      return (
        <g>
          <path d="M-14 -4 Q0 -1 14 -4 Q12 13 0 13 Q-12 13 -14 -4Z" {...filled} />
          <path d="M-7 9 Q0 4 7 9 Q4 12.5 0 12.5 Q-4 12.5 -7 9Z" fill={C.tongue} />
        </g>
      );
    case "teeth":
      return (
        <g>
          <path d="M-13 -3 L13 -4 Q11 8 0 8 Q-11 8 -13 -3Z" fill={C.teeth} stroke={C.ink} strokeWidth={3} strokeLinejoin="round" />
          <path d="M-11 2 L11 1.5" stroke={C.ink} strokeWidth={1.8} />
        </g>
      );
    case "laugh":
      return (
        <g>
          <path d="M-16 -6 Q0 -3 16 -6 Q14 19 0 19 Q-14 19 -16 -6Z" {...filled} />
          <path d="M-13 -4.5 Q0 -2 13 -4.5 L12 0 Q0 2 -12 0Z" fill={C.teeth} />
          <path d="M-9 14 Q0 7 9 14 Q5 18.5 0 18.5 Q-5 18.5 -9 14Z" fill={C.tongue} />
        </g>
      );
    case "talk": {
      const h = 2 + open * 12;
      return (
        <g>
          <path d={`M-10 -2 Q0 0 10 -2 Q9 ${h} 0 ${h + 1} Q-9 ${h} -10 -2Z`} {...filled} />
          {open > 0.35 && <ellipse cx={0} cy={h - 2} rx={4.5} ry={2} fill={C.tongue} />}
        </g>
      );
    }
  }
};

const ExtraFx: React.FC<{ kind: ArkaExpression["extra"]; fx: number; t: number }> = ({ kind, fx, t }) => {
  if (kind === "sparkle") {
    const s = 0.8 + 0.25 * Math.sin(t * 6);
    return (
      <g>
        <path d={sparklePath(11 * s)} transform={`translate(${fx + 74} -92)`} fill={C.glow} stroke={C.ink} strokeWidth={2.2} strokeLinejoin="round" />
        <path d={sparklePath(6 * (1.8 - s))} transform={`translate(${fx + 86} -64)`} fill={C.glow} stroke={C.ink} strokeWidth={1.8} strokeLinejoin="round" />
        <path d={sparklePath(5 * s)} transform={`translate(${fx - 78} -84)`} fill={C.glow} stroke={C.ink} strokeWidth={1.6} strokeLinejoin="round" />
      </g>
    );
  }
  if (kind === "sweat") {
    const dy = (t * 10) % 6;
    return (
      <path
        d="M0 -10 Q8 2 0 6 Q-8 2 0 -10Z"
        transform={`translate(${fx + 66} ${-78 + dy})`}
        fill="#8CC8F0"
        stroke={C.ink}
        strokeWidth={2.4}
        strokeLinejoin="round"
      />
    );
  }
  if (kind === "question") {
    const bob = Math.sin(t * 4) * 2;
    return (
      <g transform={`translate(${fx + 78} ${-104 + bob}) rotate(12)`}>
        <path d="M-7 -8 Q-7 -18 2 -18 Q11 -18 11 -10 Q11 -4 3 0 L3 6" fill="none" stroke={C.ink} strokeWidth={8.5} strokeLinecap="round" strokeLinejoin="round" />
        <path d="M-7 -8 Q-7 -18 2 -18 Q11 -18 11 -10 Q11 -4 3 0 L3 6" fill="none" stroke={C.glow} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={3} cy={15} r={4.4} fill={C.glow} stroke={C.ink} strokeWidth={2.2} />
      </g>
    );
  }
  if (kind === "shock") {
    return (
      <g stroke={C.ink} strokeWidth={4} strokeLinecap="round">
        <path d={`M${fx + 64} -116 L${fx + 76} -132`} />
        <path d={`M${fx + 76} -100 L${fx + 94} -108`} />
        <path d={`M${fx - 62} -116 L${fx - 74} -132`} />
      </g>
    );
  }
  return null;
};

const Leaf: React.FC<{ x: number; y: number; r: number; s?: number }> = ({ x, y, r, s = 1 }) => (
  <g transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`}>
    <path d="M0 0 C8 -10 24 -12 34 -3 C24 5 8 6 0 0Z" fill={C.leaf} {...ink} strokeWidth={2.6} />
    <path d="M3 0 Q17 -2 30 -3" fill="none" stroke={C.leafDark} strokeWidth={2} strokeLinecap="round" />
  </g>
);

const Head: React.FC<{ expr: ArkaExpression; turn: number; uid: string; blink: number; t: number }> = ({ expr, turn, uid, blink, t }) => {
  const fx = 7 * turn;
  const farR = turn >= 0;
  const face = `M${fx - 56} -76 C${fx - 58} -118 ${fx + 58} -118 ${fx + 56} -76 C${fx + 56} -46 ${fx + 38} -15 ${fx + 7} -6 Q${fx + 3} -5 ${fx - 1} -6 C${fx - 36} -14 ${fx - 56} -44 ${fx - 56} -76Z`;
  const hx = fx * 0.4;
  const backHair = `M${hx - 66} -96 C${hx - 70} -142 ${hx + 68} -144 ${hx + 66} -96 L${hx + 72} -58 L${hx + 60} -68 L${hx + 62} -38 L${hx + 50} -58 L${hx + 40} -72 L${hx - 40} -72 L${hx - 50} -58 L${hx - 64} -38 L${hx - 60} -68 L${hx - 74} -56Z`;
  const fringe = `M${fx - 61} -76 C${fx - 63} -106 ${fx - 40} -114 ${fx} -114 C${fx + 40} -114 ${fx + 63} -106 ${fx + 61} -78 L${fx + 53} -64 L${fx + 47} -82 L${fx + 37} -66 L${fx + 31} -86 L${fx + 19} -69 L${fx + 11} -88 L${fx - 1} -70 L${fx - 10} -88 L${fx - 22} -69 L${fx - 29} -86 L${fx - 40} -66 L${fx - 45} -82 L${fx - 57} -58Z`;
  const crown = `M${fx - 52} -104 C${fx - 56} -152 ${fx - 32} -172 ${fx + 2} -172 C${fx + 36} -172 ${fx + 58} -152 ${fx + 54} -104 Q${fx + 2} -92 ${fx - 52} -104Z`;
  const eL = { x: fx - 23, y: -54 };
  const eR = { x: fx + 23, y: -54 };
  return (
    <g>
      <defs>
        <clipPath id={`${uid}-face`}>
          <path d={face} />
        </clipPath>
        <clipPath id={`${uid}-faceHair`}>
          <path d={face} />
          <path d={fringe} />
        </clipPath>
        <clipPath id={`${uid}-crown`}>
          <path d={crown} />
        </clipPath>
      </defs>
      {/* back hair */}
      <path d={backHair} fill={C.hair} {...ink} />
      <path d={`M${hx + 50} -58 L${hx + 62} -38 L${hx + 60} -68Z`} fill={C.hairShade} />
      {/* ears */}
      <g>
        <ellipse cx={fx - 56} cy={-56} rx={8.5} ry={11.5} fill={C.skin} {...ink} />
        <path d={`M${fx - 57} -61 Q${fx - 61} -56 ${fx - 56} -51`} fill="none" stroke={C.skinShade} strokeWidth={2.6} strokeLinecap="round" />
        <ellipse cx={fx + 55} cy={-56} rx={7.5} ry={11} fill={C.skin} {...ink} />
      </g>
      {/* face */}
      <path d={face} fill={C.skin} {...ink} />
      <g clipPath={`url(#${uid}-face)`}>
        <ellipse cx={fx + (farR ? 60 : -60)} cy={-46} rx={22} ry={46} fill={C.skinShade} opacity={0.45} />
        <ellipse cx={fx} cy={-6} rx={30} ry={10} fill={C.skinShade} opacity={0.35} />
      </g>
      {/* blush */}
      <ellipse cx={fx - 32} cy={-34} rx={10} ry={5.5} fill={C.blush} opacity={expr.blush} />
      <ellipse cx={fx + 33} cy={-34} rx={9} ry={5.5} fill={C.blush} opacity={expr.blush} />
      {/* eyes */}
      <Eye cx={eL.x} cy={eL.y} e={expr.eyeL} far={!farR} side="L" uid={uid} blink={blink} t={t} />
      <Eye cx={eR.x} cy={eR.y} e={expr.eyeR} far={farR} side="R" uid={uid} blink={blink} t={t} />
      {/* nose + mouth */}
      <path d={`M${fx + 5} -41 q2.5 2.4 -0.5 3.6`} fill="none" stroke={C.skinShade} strokeWidth={2.6} strokeLinecap="round" />
      <g transform={`translate(${fx + 3} -24)`}>
        <Mouth kind={expr.mouth} open={expr.mouthOpen} />
      </g>
      {/* fringe */}
      <path d={fringe} fill={C.hair} {...ink} />
      <path
        d={`M${fx - 38} -100 Q${fx - 10} -108 ${fx + 22} -102 M${fx + 30} -100 Q${fx + 40} -98 ${fx + 46} -94`}
        fill="none"
        stroke={C.hairLight}
        strokeWidth={4}
        strokeLinecap="round"
      />
      <path d={`M${fx + 37} -66 L${fx + 31} -86 L${fx + 25} -76Z M${fx - 1} -70 L${fx - 10} -88 L${fx - 6} -76Z`} fill={C.hairShade} opacity={0.8} />
      {/* hat shadow over hair + forehead */}
      <g clipPath={`url(#${uid}-faceHair)`}>
        <ellipse cx={fx + 2} cy={-106} rx={66} ry={14} fill={C.ink} opacity={0.15} />
      </g>
      {/* brows over hair (anime convention) */}
      <BrowShape cx={eL.x} cy={-80} b={expr.browL} side="L" />
      <BrowShape cx={eR.x} cy={-80} b={expr.browR} side="R" />
      {/* hat */}
      <g transform={`translate(0 -11) rotate(-4 ${fx} -104)`}>
        <ellipse cx={fx + 3} cy={-97} rx={107} ry={22} fill={C.hatShade} {...ink} />
        <ellipse cx={fx + 3} cy={-101} rx={105} ry={20} fill={C.hat} />
        <ellipse cx={fx + 3} cy={-101} rx={92} ry={15} fill="none" stroke={C.hatShade} strokeWidth={2} strokeDasharray="5 6" />
        <path d={`M${fx - 102} -98 Q${fx + 3} -74 ${fx + 108} -98`} fill="none" stroke={C.ink} strokeWidth={SW} strokeLinecap="round" />
        <path d={crown} fill={C.hat} {...ink} />
        <g clipPath={`url(#${uid}-crown)`}>
          <ellipse cx={fx + 44} cy={-130} rx={20} ry={50} fill={C.hatShade} opacity={0.8} />
          <ellipse cx={fx - 22} cy={-156} rx={18} ry={8} fill="#fff" opacity={0.7} />
          <path d={`M${fx - 54} -118 Q${fx + 2} -108 ${fx + 56} -118 L${fx + 56} -96 L${fx - 54} -96Z`} fill={C.band} />
          <path d={`M${fx - 54} -116 Q${fx + 2} -106 ${fx + 56} -116`} fill="none" stroke={C.packLight} strokeWidth={2} />
        </g>
        <path d={crown} fill="none" {...ink} />
        <path d={`M${fx - 2} -168 Q${fx + 4} -152 ${fx} -138`} fill="none" stroke={C.hatShade} strokeWidth={3} strokeLinecap="round" />
        <Leaf x={fx + 26} y={-112} r={-62} s={0.95} />
        <Leaf x={fx + 30} y={-110} r={-24} s={0.8} />
        {/* brass compass-rose pin (expedition badge) */}
        <g transform={`translate(${fx + 22} -110)`}>
          <circle r={10.5} fill={C.brass} stroke={C.ink} strokeWidth={2.4} />
          <circle r={7.6} fill={C.navy} />
          <path d={sparklePath(7, 0.3)} fill={C.brassLight} />
          <path d={sparklePath(4.6, 0.3)} transform="rotate(45)" fill={C.brassLight} opacity={0.75} />
          <path d="M0 -7 L1.6 0 L-1.6 0Z" fill={C.route} />
          <circle r={1.3} fill={C.ink} />
          <path d="M-6.5 -5 Q-3 -9 1 -9" fill="none" stroke="#fff" strokeWidth={1.6} strokeLinecap="round" opacity={0.7} />
        </g>
      </g>
      <ExtraFx kind={expr.extra} fx={fx} t={t} />
    </g>
  );
};

/* ------------------------------- props ----------------------------- */

const MapProp: React.FC<{ hL: Vec; hR: Vec }> = ({ hL, hR }) => {
  const cx = (hL.x + hR.x) / 2;
  const cy = (hL.y + hR.y) / 2 - 6;
  const W = clamp(Math.abs(hR.x - hL.x) + 16, 60, 150);
  const H = 66;
  const ang = deg(Math.atan2(hR.y - hL.y, hR.x - hL.x));
  const xs = [0, 1, 2, 3].map((i) => -W / 2 + (W / 3) * i);
  const o = [0, -4, 2, -3];
  const panel = (i: number) =>
    `M${xs[i]} ${-H / 2 + o[i]} L${xs[i + 1]} ${-H / 2 + o[i + 1]} L${xs[i + 1]} ${H / 2 + o[i + 1]} L${xs[i]} ${H / 2 + o[i]}Z`;
  const outline = `M${xs[0]} ${-H / 2 + o[0]} L${xs[1]} ${-H / 2 + o[1]} L${xs[2]} ${-H / 2 + o[2]} L${xs[3]} ${-H / 2 + o[3]} L${xs[3]} ${H / 2 + o[3]} L${xs[2]} ${H / 2 + o[2]} L${xs[1]} ${H / 2 + o[1]} L${xs[0]} ${H / 2 + o[0]}Z`;
  return (
    <g transform={`translate(${cx} ${cy}) rotate(${ang})`}>
      <path d={outline} fill={C.paper} />
      <path d={`M${-W / 2} 10 C${-W / 4} 0 ${-W / 8} 26 ${W / 6} 14 S${W / 2.4} 4 ${W / 2} 12 L${W / 2} ${H / 2} L${-W / 2} ${H / 2}Z`} fill={C.water} opacity={0.55} />
      <path d={`M${-W / 2 + 6} -18 C${-W / 6} -30 ${W / 8} -10 ${W / 3} -22 S${W / 2} -8 ${W / 2 - 4} 0 C${W / 6} 6 ${-W / 6} -6 ${-W / 2 + 4} 4Z`} fill={C.land} opacity={0.7} />
      <path d={`M${-W / 4} -12 l7 -12 l7 12Z M${-W / 4 + 10} -12 l6 -9 l6 9Z`} fill={C.paperDark} stroke={C.paperLine} strokeWidth={1.4} strokeLinejoin="round" />
      <path d={`M${-W / 2 + 10} 22 C${-W / 5} 4 ${-W / 10} -4 ${W / 7} -8 S${W / 3} -16 ${W / 3 + 4} -18`} fill="none" stroke={C.route} strokeWidth={2.6} strokeDasharray="4 4" strokeLinecap="round" />
      <path d={`M${W / 3} -24 l9 9 M${W / 3 + 9} -24 l-9 9`} stroke={C.route} strokeWidth={3.4} strokeLinecap="round" />
      <path d={panel(1)} fill={C.ink} opacity={0.08} />
      <path d={panel(2)} fill="#fff" opacity={0.18} />
      <path d={`M${xs[1]} ${-H / 2 + o[1]} L${xs[1]} ${H / 2 + o[1]} M${xs[2]} ${-H / 2 + o[2]} L${xs[2]} ${H / 2 + o[2]}`} stroke={C.paperLine} strokeWidth={1.6} />
      <path d={outline} fill="none" {...ink} />
    </g>
  );
};

const Compass: React.FC<{ at: Vec; t: number }> = ({ at, t }) => {
  const needle = -28 + Math.sin(t * 3.1) * 18 + Math.sin(t * 7.3) * 5;
  return (
    <g transform={`translate(${at.x - 3} ${at.y - 16})`}>
      <circle cx={0} cy={-19} r={4.5} fill="none" stroke={C.ink} strokeWidth={5.5} />
      <circle cx={0} cy={-19} r={4.5} fill="none" stroke={C.brass} strokeWidth={2.4} />
      <circle r={17} fill={C.brass} {...ink} />
      <circle r={12.5} fill={C.hat} stroke={C.brassDark} strokeWidth={2} />
      {[0, 90, 180, 270].map((a) => (
        <path key={a} d="M0 -11 L0 -8" transform={`rotate(${a})`} stroke={C.ink} strokeWidth={1.8} strokeLinecap="round" />
      ))}
      <g transform={`rotate(${needle.toFixed(2)})`}>
        <path d="M0 -10 L3 0 L-3 0Z" fill={C.route} />
        <path d="M0 10 L3 0 L-3 0Z" fill={C.navy} />
      </g>
      <circle r={1.8} fill={C.brassLight} stroke={C.ink} strokeWidth={1} />
      <path d="M-9 -9 Q-4 -13 2 -12.5" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" opacity={0.8} />
    </g>
  );
};

const Spyglass: React.FC<{ eye: Vec; hand: Vec }> = ({ eye, hand }) => {
  const dx = hand.x - eye.x;
  const dy = hand.y - eye.y;
  const m = Math.hypot(dx, dy) || 1;
  const u = { x: dx / m, y: dy / m };
  const at = (s: number) => ({ x: eye.x + u.x * s, y: eye.y + u.y * s });
  const seg = (s0: number, s1: number, w: number, c: string) => (
    <Stroked d={`M${P(at(s0))} L${P(at(s1))}`} w={w} color={c} cap="butt" />
  );
  return (
    <g>
      {seg(4, 34, 13, C.brass)}
      {seg(34, 64, 16, C.pack)}
      {seg(64, 98, 20, C.brass)}
      {seg(94, 100, 23, C.brassDark)}
      <path d={`M${P(at(70))} L${P(at(92))}`} transform={`translate(${-u.y * 5} ${u.x * 5})`} stroke={C.brassLight} strokeWidth={3} strokeLinecap="round" />
      <path d={`M${P(at(8))} L${P(at(30))}`} transform={`translate(${-u.y * 3} ${u.x * 3})`} stroke={C.brassLight} strokeWidth={2.4} strokeLinecap="round" />
    </g>
  );
};

/* ------------------------------- torso ----------------------------- */

const SHIRT =
  "M-30 -106 C-44 -104 -48 -96 -47 -84 L-43 2 Q0 11 43 2 L47 -84 C48 -96 44 -104 30 -106 Q0 -96 -30 -106Z";

const Backpack: React.FC = () => (
  <g>
    <rect x={-58} y={-104} width={116} height={84} rx={18} fill={C.pack} {...ink} />
    <rect x={44} y={-96} width={14} height={70} rx={7} fill={C.packDark} opacity={0.7} />
    <rect x={-66} y={-116} width={132} height={22} rx={11} fill={C.bedroll} {...ink} />
    <path d="M-66 -105 L66 -105" stroke={C.bedrollDark} strokeWidth={2} opacity={0.6} />
    <ellipse cx={-62} cy={-105} rx={5} ry={10} fill={C.bedrollDark} stroke={C.ink} strokeWidth={2} />
    <ellipse cx={62} cy={-105} rx={5} ry={10} fill={C.bedrollDark} stroke={C.ink} strokeWidth={2} />
    <rect x={-50} y={-118} width={7} height={26} rx={2} fill={C.strap} stroke={C.ink} strokeWidth={2} />
    <rect x={43} y={-118} width={7} height={26} rx={2} fill={C.strap} stroke={C.ink} strokeWidth={2} />
  </g>
);

const Torso: React.FC = () => (
  <g>
    <path d={SHIRT} fill={C.shirt} {...ink} />
    <path d="M20 -100 C34 -98 40 -92 40 -84 L38 4 Q42 3 43 2 L47 -84 C48 -96 44 -104 30 -106Z" fill={C.shirtShade} />
    <path d="M-42 -8 Q0 2 42 -8 L43 2 Q0 11 -43 2Z" fill={C.shirtShade} opacity={0.8} />
    <path d={SHIRT} fill="none" {...ink} />
    {/* collar */}
    <path d="M-10 -104 L10 -104 L0 -84Z" fill={C.skinShade} />
    <path d="M-2 -99 L-25 -105 L-15 -82Z" fill={C.shirt} {...ink} strokeWidth={2.6} />
    <path d="M2 -99 L25 -105 L15 -82Z" fill={C.shirt} {...ink} strokeWidth={2.6} />
    {/* placket + buttons */}
    <path d="M0 -84 L0 4" stroke={C.shirtShade} strokeWidth={2.4} />
    <circle cx={0} cy={-62} r={2.2} fill={C.brass} />
    <circle cx={0} cy={-38} r={2.2} fill={C.brass} />
    {/* chest pocket */}
    <rect x={-35} y={-74} width={20} height={19} rx={3} fill={C.shirt} {...ink} strokeWidth={2.4} />
    <path d="M-36 -74 L-14 -74 L-16 -66 L-34 -66Z" fill={C.shirtShade} stroke={C.ink} strokeWidth={2.2} strokeLinejoin="round" />
    <circle cx={-25} cy={-68} r={2} fill={C.brass} />
    {/* straps */}
    <path d="M-34 -104 C-36 -84 -34 -64 -29 -36" fill="none" stroke={C.ink} strokeWidth={12.5} strokeLinecap="round" />
    <path d="M-34 -104 C-36 -84 -34 -64 -29 -36" fill="none" stroke={C.strap} strokeWidth={8} strokeLinecap="round" />
    <path d="M34 -104 C36 -84 34 -64 29 -36" fill="none" stroke={C.ink} strokeWidth={12.5} strokeLinecap="round" />
    <path d="M34 -104 C36 -84 34 -64 29 -36" fill="none" stroke={C.strap} strokeWidth={8} strokeLinecap="round" />
    <rect x={-37} y={-60} width={12} height={9} rx={2} fill="none" stroke={C.brass} strokeWidth={2.6} />
    <rect x={25} y={-60} width={12} height={9} rx={2} fill="none" stroke={C.brass} strokeWidth={2.6} />
  </g>
);

const Shorts: React.FC<{ hipY: number }> = ({ hipY }) => (
  <g>
    <path d={`M-40 ${hipY - 26} L40 ${hipY - 26} L43 ${hipY + 14} Q0 ${hipY + 20} -43 ${hipY + 14}Z`} fill={C.shorts} {...ink} />
    <path d={`M0 ${hipY - 6} L0 ${hipY + 16}`} stroke={C.shortsShade} strokeWidth={2.6} strokeLinecap="round" />
    <rect x={-46} y={hipY - 2} width={11} height={15} rx={2.5} fill={C.shortsShade} stroke={C.ink} strokeWidth={2.2} />
  </g>
);

const Neck: React.FC = () => <rect x={-9} y={-116} width={18} height={18} rx={4} fill={C.skinShade} stroke={C.ink} strokeWidth={2.4} />;

const ScarfWrap: React.FC<{ t: number }> = ({ t }) => {
  const sway = Math.sin(t * 4) * 2;
  return (
    <g>
      <path d={`M12 -92 Q${16 + sway} -74 ${22 + sway * 1.6} -60 L${10 + sway * 1.6} -58 Q${8 + sway} -74 6 -90Z`} fill={C.scarf} {...ink} strokeWidth={2.8} />
      <path d={`M16 -92 Q${26 + sway} -80 ${34 + sway * 1.4} -68 L${24 + sway * 1.4} -64 Q${18 + sway} -78 10 -90Z`} fill={C.scarfDark} {...ink} strokeWidth={2.8} />
      <path d="M-32 -108 Q0 -98 32 -108 Q38 -98 32 -89 Q0 -79 -32 -89 Q-38 -98 -32 -108Z" fill={C.scarf} {...ink} />
      <path d="M-30 -94 Q0 -84 30 -94 L32 -89 Q0 -79 -32 -89Z" fill={C.scarfDark} opacity={0.5} />
      <path d="M-24 -103 Q-6 -97 10 -100" fill="none" stroke={C.scarfLight} strokeWidth={3} strokeLinecap="round" />
      <ellipse cx={13} cy={-92} rx={9} ry={8} fill={C.scarf} {...ink} strokeWidth={2.8} />
      <path d="M8 -95 Q13 -98 17 -94" fill="none" stroke={C.scarfLight} strokeWidth={2.2} strokeLinecap="round" />
    </g>
  );
};

/* ------------------------------- ARKA ------------------------------ */

export const Arka: React.FC<ArkaProps> = ({
  pose,
  expression,
  t = 0,
  blink = 1,
  facing = 1,
  shadow = true,
  uid = "arka",
  breathe = true,
  overlap = { y: 0, tilt: 0 },
}) => {
  const lagY = clamp(overlap.y, -7, 7);
  const lagTilt = clamp(overlap.tilt, -6, 6);
  const propS = clamp(pose.propScale ?? 1, 0, 1);
  const scaled = (c: Vec, node: React.ReactNode) =>
    propS >= 0.999 ? node : (
      <g transform={`translate(${P(c)}) scale(${propS.toFixed(3)}) translate(${(-c.x).toFixed(2)} ${(-c.y).toFixed(2)})`}
        opacity={Math.min(1, propS * 1.6)}>{node}</g>
    );
  const br = breathe ? Math.sin(t * 2.4) : 0;
  const hipY = HIP_Y + pose.crouch;
  const handL = { x: pose.handL.x, y: pose.handL.y + br * 0.9 };
  const handR = { x: pose.handR.x, y: pose.handR.y + br * 0.9 };
  const armL = solveArm("L", handL);
  const armR = solveArm("R", handR);
  const legL = solveLeg("L", hipY, pose.footL);
  const legR = solveLeg("R", hipY, pose.footR);
  const headY = NECK_Y - br * 1.1;
  const torsoT = `translate(0 ${hipY}) rotate(${pose.lean.toFixed(2)})`;
  const sx = 1 + pose.squash * 0.6;
  const sy = 1 - pose.squash;
  const air = clamp(-pose.rootY / 120, 0, 0.6);
  const handAngle = (l: Limb) => deg(Math.atan2(l.end.y - l.mid.y, l.end.x - l.mid.x)) - 90;
  const fx = 7 * pose.turn;
  const eyeTorso = rotateAround({ x: (fx + 23) * HEAD_SCALE, y: headY - 54 * HEAD_SCALE }, { x: 0, y: headY }, pose.headTilt);
  const liftL = clamp((-12 - pose.footL.y) / 30, 0, 1);
  const liftR = clamp((-12 - pose.footR.y) / 30, 0, 1);

  return (
    <g>
      {shadow && (
        <ellipse cx={pose.rootX} cy={2} rx={78 * (1 - air * 0.6)} ry={11 * (1 - air * 0.5)} fill={C.ink} opacity={0.16 * (1 - air)} />
      )}
      <g transform={`translate(${pose.rootX.toFixed(2)} ${pose.rootY.toFixed(2)}) scale(${facing} 1) scale(${sx.toFixed(4)} ${sy.toFixed(4)})`}>
        {/* back layer */}
        <g transform={torsoT}>
          <Scarf t={t} wind={pose.scarfWind} />
          <Backpack />
        </g>
        {/* legs */}
        <LegShape l={legL} />
        <LegShape l={legR} />
        <Shoe at={legL.end} mirror={false} lift={liftL} />
        <Shoe at={legR.end} mirror={true} lift={liftR} />
        <Shorts hipY={hipY} />
        {/* torso + arms + head */}
        <g transform={torsoT}>
          <Neck />
          <Torso />
          <ArmShape l={armL} cuff={true} />
          <ArmShape l={armR} cuff={false} />
          <ScarfWrap t={t} />
          <g transform={`translate(0 ${(headY + lagY).toFixed(2)}) rotate(${(pose.headTilt + lagTilt).toFixed(2)}) scale(${HEAD_SCALE})`}>
            <Head expr={expression} turn={pose.turn} uid={uid} blink={blink} t={t} />
          </g>
          {pose.prop === "map" && propS > 0.01 && scaled(along(armL.end, armR.end, 0.5), <MapProp hL={armL.end} hR={armR.end} />)}
          {pose.prop === "spyglass" && propS > 0.01 && scaled(armR.end, <Spyglass eye={eyeTorso} hand={armR.end} />)}
          {pose.prop === "compass" && propS > 0.01 && scaled(armR.end, <Compass at={armR.end} t={t} />)}
          <Hand at={armL.end} angle={handAngle(armL)} shape={pose.handShapeL} mirror={false} />
          <Hand at={armR.end} angle={handAngle(armR)} shape={pose.handShapeR} mirror={true} />
        </g>
      </g>
    </g>
  );
};

/** Bounding box of the rig in root space (for standalone SVGs). */
export const ARKA_VIEWBOX = { x: -150, y: -440, w: 300, h: 460 };
