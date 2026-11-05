// Background kit (M2 SVG scene library): reusable outlined elements in the Arka & Lipa
// style — ink-plum outlines, the rig palette, one soft shade per shape, gentle ambient motion.
// All coordinates are world pixels (1920x1080 frame); every helper is a pure function of
// its props + frame, so renders are deterministic.
import React from "react";
import { C as R } from "../../rig/palette";
import { H, W } from "../layout";

export const X0 = -W;
export const Y0 = -0.6 * H;
export const WW = 3 * W;
export const HH = 2.2 * H;
export const INK = R.ink;
export const OUT = 5; // outline width in world px (thicker than the rig: backgrounds are seen small)

export const ol = (w = OUT) => ({ stroke: INK, strokeWidth: w, strokeLinejoin: "round" as const, strokeLinecap: "round" as const });

export const rnd = (i: number) => {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};

/** A world-sized SVG layer that extends far past the frame (pans and zoom-outs never show an edge). */
export const Layer: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <svg viewBox={`${X0} ${Y0} ${WW} ${HH}`} width={WW} height={HH}
    style={{ position: "absolute", left: X0, top: Y0, overflow: "visible" }}>
    {children}
  </svg>
);

/** Full-bleed vertical gradient sky/wall. `id` must be unique per theme. */
export const Backdrop: React.FC<{ id: string; stops: [number, string][] }> = ({ id, stops }) => (
  <>
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        {stops.map(([o, c]) => <stop key={o} offset={o} stopColor={c} />)}
      </linearGradient>
    </defs>
    <rect x={X0} y={Y0} width={WW} height={HH} fill={`url(#${id})`} />
  </>
);

/** Ground band from y down, with an optional wavy top edge. */
export const Ground: React.FC<{ y: number; color: string; shade?: string; amp?: number; seed?: number; outline?: boolean }> = ({
  y, color, shade, amp = 0, seed = 1, outline = true,
}) => {
  const pts: string[] = [];
  const n = 48;
  for (let i = 0; i <= n; i++) {
    const x = X0 + (i / n) * WW;
    const yy = y + amp * (Math.sin(i * 0.9 + seed) * 0.6 + Math.sin(i * 0.37 + seed * 2) * 0.4);
    pts.push(`${x.toFixed(1)} ${yy.toFixed(1)}`);
  }
  const top = "M" + pts.join(" L");
  return (
    <g>
      <path d={`${top} L${X0 + WW} ${Y0 + HH} L${X0} ${Y0 + HH}Z`} fill={color} />
      {shade && <path d={`${top} L${X0 + WW} ${Y0 + HH} L${X0} ${Y0 + HH}Z`} fill={shade} opacity={0.35} transform="translate(0 46)" />}
      {outline && <path d={top} fill="none" {...ol()} />}
    </g>
  );
};

/** Rolling hills band (smooth bumps) — far/mid scenery. */
export const Hills: React.FC<{ y: number; amp: number; color: string; shade?: string; seed?: number; bumps?: number }> = ({
  y, amp, color, shade, seed = 0, bumps = 9,
}) => {
  let d = `M${X0} ${y}`;
  const step = WW / bumps;
  for (let i = 0; i < bumps; i++) {
    const x1 = X0 + i * step;
    const h = amp * (0.55 + rnd(seed + i) * 0.45);
    d += ` C${x1 + step * 0.25} ${y - h} ${x1 + step * 0.75} ${y - h} ${x1 + step} ${y}`;
  }
  const body = `${d} L${X0 + WW} ${Y0 + HH} L${X0} ${Y0 + HH}Z`;
  return (
    <g>
      <path d={body} fill={color} />
      {shade && <path d={body} fill={shade} opacity={0.3} transform={`translate(0 ${amp * 0.45})`} />}
      <path d={d} fill="none" {...ol()} />
    </g>
  );
};

/** Jagged mountain range with optional snow caps. */
export const Mountains: React.FC<{ base: number; height: number; color: string; shade: string; snow?: boolean; seed?: number; n?: number }> = ({
  base, height, color, shade, snow = false, seed = 0, n = 8,
}) => {
  const step = WW / n;
  return (
    <g>
      {Array.from({ length: n + 1 }, (_, i) => {
        const cx = X0 + i * step + (rnd(seed + i) - 0.5) * step * 0.4;
        const h = height * (0.6 + rnd(seed + i + 20) * 0.4);
        const w = step * (0.75 + rnd(seed + i + 40) * 0.35);
        const peak = `${cx} ${base - h}`;
        const snowY = base - h * 0.72;
        return (
          <g key={i}>
            <path d={`M${cx - w} ${base} L${peak} L${cx + w} ${base}Z`} fill={color} {...ol()} />
            <path d={`M${cx} ${base - h} L${cx + w} ${base} L${cx + w * 0.15} ${base}Z`} fill={shade} opacity={0.55} />
            {snow && (
              <path d={`M${cx - w * 0.28} ${snowY} L${peak} L${cx + w * 0.28} ${snowY} L${cx + w * 0.12} ${snowY + 18} L${cx} ${snowY + 4} L${cx - w * 0.12} ${snowY + 20}Z`}
                fill="#FFFFFF" {...ol(OUT * 0.8)} />
            )}
          </g>
        );
      })}
    </g>
  );
};

/** Puffy outlined cloud drifting with the frame. */
export const Cloud: React.FC<{ x: number; y: number; s?: number; f: number; speed?: number; tint?: string; shade?: string }> = ({
  x, y, s = 1, f, speed = 0.3, tint = "#FFFFFF", shade = "#DCE8F5",
}) => {
  const dx = ((x - X0 + f * speed) % WW) + X0;
  const d = "M-120 20 C-150 20 -150 -20 -112 -24 C-110 -62 -52 -70 -36 -40 C-20 -86 52 -86 62 -36 C96 -60 140 -28 120 6 C150 14 140 40 112 40 L-96 40 C-126 40 -132 22 -120 20Z";
  return (
    <g transform={`translate(${dx.toFixed(1)} ${y}) scale(${s})`}>
      <path d={d} fill={tint} {...ol(OUT / s)} />
      <path d="M-104 30 C-60 40 60 42 112 28 L112 40 L-96 40Z" fill={shade} opacity={0.8} />
    </g>
  );
};

export const Clouds: React.FC<{ f: number; y: number; n: number; spread?: number; seed?: number; tint?: string; shade?: string; speed?: number }> = ({
  f, y, n, spread = 260, seed = 5, tint, shade, speed = 0.3,
}) => (
  <g>
    {Array.from({ length: n }, (_, i) => (
      <Cloud key={i} x={X0 + rnd(seed + i) * WW} y={y + rnd(seed + i + 9) * spread} s={0.7 + rnd(seed + i + 3) * 0.7}
        f={f} speed={speed * (0.6 + rnd(seed + i + 4) * 0.8)} tint={tint} shade={shade} />
    ))}
  </g>
);

/** Sun with slowly turning rays. */
export const Sun: React.FC<{ x: number; y: number; r: number; f: number; color?: string; rays?: boolean }> = ({
  x, y, r, f, color = R.glow, rays = true,
}) => (
  <g transform={`translate(${x} ${y})`}>
    <circle r={r * 1.9} fill={color} opacity={0.18} />
    {rays && (
      <g transform={`rotate(${(f * 0.15).toFixed(2)})`}>
        {Array.from({ length: 12 }, (_, i) => (
          <path key={i} d={`M0 ${-r * 1.18} L${r * 0.12} ${-r * 1.5} L${-r * 0.12} ${-r * 1.5}Z`} transform={`rotate(${i * 30})`}
            fill={color} {...ol(OUT * 0.7)} />
        ))}
      </g>
    )}
    <circle r={r} fill={color} {...ol()} />
    <circle cx={-r * 0.3} cy={-r * 0.3} r={r * 0.28} fill="#FFFFFF" opacity={0.45} />
  </g>
);

/** Twinkling stars over the whole layer. */
export const Stars: React.FC<{ f: number; n: number; seed?: number; yMax?: number }> = ({ f, n, seed = 3, yMax = 0.7 * H }) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const x = X0 + rnd(seed + i) * WW;
      const y = Y0 + rnd(seed + i + 50) * (yMax - Y0);
      const tw = 0.55 + 0.45 * Math.sin(f / (9 + rnd(i) * 14) + i);
      const big = rnd(seed + i + 90) > 0.86;
      return big ? (
        <path key={i} d="M0 -10 L2.6 -2.6 L10 0 L2.6 2.6 L0 10 L-2.6 2.6 L-10 0 L-2.6 -2.6Z" transform={`translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${(0.8 + tw * 0.6).toFixed(2)})`}
          fill={R.glow} opacity={tw} />
      ) : <circle key={i} cx={x} cy={y} r={1.6 + rnd(i + 7) * 1.8} fill="#FFFFFF" opacity={tw} />;
    })}
  </g>
);

/** Round deciduous tree that sways a little. */
export const Tree: React.FC<{ x: number; y: number; s?: number; f: number; leaf?: string; leafShade?: string; seed?: number }> = ({
  x, y, s = 1, f, leaf = R.leaf, leafShade = R.leafDark, seed = 0,
}) => {
  const sway = Math.sin(f / 40 + seed) * 1.6;
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-14 0 L-10 -120 L10 -120 L14 0Z" fill={R.pack} {...ol(OUT / s)} />
      <g transform={`rotate(${sway.toFixed(2)} 0 -110)`}>
        <path d="M0 -300 C70 -300 110 -250 100 -200 C140 -180 130 -110 80 -105 C60 -80 -60 -80 -80 -105 C-130 -110 -140 -180 -100 -200 C-110 -250 -70 -300 0 -300Z"
          fill={leaf} {...ol(OUT / s)} />
        <path d="M-80 -108 C-40 -92 50 -92 80 -108 C110 -120 120 -150 112 -170 C80 -130 -60 -124 -112 -160 C-120 -130 -100 -114 -80 -108Z" fill={leafShade} opacity={0.7} />
        <circle cx={-34} cy={-240} r={14} fill="#FFFFFF" opacity={0.25} />
      </g>
    </g>
  );
};

/** Pine tree (forests, mountains, snow). */
export const Pine: React.FC<{ x: number; y: number; s?: number; f: number; color?: string; shade?: string; snow?: boolean; seed?: number }> = ({
  x, y, s = 1, f, color = "#3E8E5A", shade = "#2C6B43", snow = false, seed = 0,
}) => {
  const sway = Math.sin(f / 45 + seed) * 1.2;
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <rect x={-10} y={-50} width={20} height={50} fill={R.packDark} {...ol(OUT / s)} />
      <g transform={`rotate(${sway.toFixed(2)} 0 -40)`}>
        {[0, 1, 2].map((k) => {
          const top = -320 + k * 80;
          const half = 70 + k * 30;
          return (
            <g key={k}>
              <path d={`M0 ${top} L${half} ${top + 150} L${-half} ${top + 150}Z`} fill={color} {...ol(OUT / s)} />
              <path d={`M0 ${top} L${half} ${top + 150} L${half * 0.2} ${top + 150}Z`} fill={shade} opacity={0.6} />
              {snow && <path d={`M0 ${top} L${half * 0.42} ${top + 62} L${half * 0.1} ${top + 52} L${-half * 0.16} ${top + 66} L${-half * 0.42} ${top + 62}Z`} fill="#FFFFFF" {...ol(OUT * 0.7 / s)} />}
            </g>
          );
        })}
      </g>
    </g>
  );
};

export const Bush: React.FC<{ x: number; y: number; s?: number; color?: string; shade?: string; berries?: boolean }> = ({
  x, y, s = 1, color = R.leaf, shade = R.leafDark, berries = false,
}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <path d="M-90 0 C-120 0 -120 -50 -80 -54 C-74 -96 -10 -100 0 -66 C14 -104 84 -96 82 -52 C120 -50 120 0 90 0Z" fill={color} {...ol(OUT / s)} />
    <path d="M-86 -6 C-40 6 40 6 86 -6 L90 0 L-90 0Z" fill={shade} opacity={0.7} />
    {berries && [[-40, -40], [20, -60], [56, -26]].map(([bx, by], i) => <circle key={i} cx={bx} cy={by} r={8} fill={R.shoe} {...ol(2.5 / s)} />)}
  </g>
);

export const Rock: React.FC<{ x: number; y: number; s?: number; color?: string; shade?: string }> = ({
  x, y, s = 1, color = "#9C97A8", shade = "#77728A",
}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <path d="M-80 0 L-64 -46 L-20 -70 L36 -62 L76 -30 L84 0Z" fill={color} {...ol(OUT / s)} />
    <path d="M36 -62 L76 -30 L84 0 L20 0 L30 -30Z" fill={shade} opacity={0.6} />
  </g>
);

/** Grass tufts and little flowers along a ground line. */
export const Tufts: React.FC<{ y: number; n: number; f: number; seed?: number; color?: string; flowers?: boolean }> = ({
  y, n, f, seed = 2, color = R.leafDark, flowers = true,
}) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const x = X0 + rnd(seed + i) * WW;
      const yy = y + rnd(seed + i + 5) * 60;
      const sway = Math.sin(f / 25 + i) * 3;
      return (
        <g key={i} transform={`translate(${x.toFixed(1)} ${yy.toFixed(1)})`}>
          <path d={`M-12 0 Q-10 -20 ${-14 + sway} -34 M0 0 Q2 -26 ${sway} -44 M12 0 Q10 -20 ${14 + sway} -32`} fill="none" stroke={color} strokeWidth={5} strokeLinecap="round" />
          {flowers && rnd(seed + i + 9) > 0.6 && (
            <g transform={`translate(${sway} -46)`}>
              {[0, 72, 144, 216, 288].map((a) => <circle key={a} cx={Math.cos((a * Math.PI) / 180) * 7} cy={Math.sin((a * Math.PI) / 180) * 7} r={6} fill={i % 2 ? R.flower : "#FFFFFF"} />)}
              <circle r={5} fill={R.flowerCore} />
            </g>
          )}
        </g>
      );
    })}
  </g>
);

/** Rising bubbles (underwater) or floating motes (pass colors). */
export const Bubbles: React.FC<{ f: number; n: number; seed?: number; color?: string; speed?: number }> = ({
  f, n, seed = 11, color = "#FFFFFF", speed = 1.2,
}) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const x = X0 + rnd(seed + i) * WW + Math.sin(f / 18 + i) * 10;
      const span = HH;
      const y = Y0 + span - ((rnd(seed + i + 3) * span + f * speed * (0.6 + rnd(i) * 0.8)) % span);
      const r = 5 + rnd(seed + i + 7) * 12;
      return (
        <g key={i} opacity={0.75}>
          <circle cx={x} cy={y} r={r} fill="none" stroke={color} strokeWidth={3} />
          <circle cx={x - r * 0.35} cy={y - r * 0.35} r={r * 0.25} fill={color} />
        </g>
      );
    })}
  </g>
);

/** Falling particles: snow, leaves or rain streaks. */
export const Fall: React.FC<{ f: number; n: number; kind: "snow" | "rain" | "leaf"; seed?: number; speed?: number }> = ({
  f, n, kind, seed = 31, speed = 2,
}) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const x = X0 + rnd(seed + i) * WW + (kind === "rain" ? 0 : Math.sin(f / 20 + i) * 24);
      const y = Y0 + ((rnd(seed + i + 4) * HH + f * speed * (0.6 + rnd(i + 2) * 0.8)) % HH);
      if (kind === "rain") return <path key={i} d={`M${x} ${y} l-8 34`} stroke="#BFD9F2" strokeWidth={3} strokeLinecap="round" opacity={0.7} />;
      if (kind === "leaf") return (
        <path key={i} d="M0 -10 C10 -6 10 6 0 10 C-10 6 -10 -6 0 -10Z" transform={`translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${(f * 3 + i * 40) % 360})`}
          fill={i % 3 ? R.leaf : "#E8A33D"} {...ol(2)} />
      );
      return <circle key={i} cx={x} cy={y} r={3 + rnd(i + 8) * 4} fill="#FFFFFF" opacity={0.9} />;
    })}
  </g>
);

/** Glowing fireflies / dust motes drifting. */
export const Motes: React.FC<{ f: number; n: number; seed?: number; color?: string; r?: number; yMin?: number; yMax?: number }> = ({
  f, n, seed = 61, color = R.glow, r = 4, yMin = Y0, yMax = Y0 + HH,
}) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const x = X0 + rnd(seed + i) * WW + Math.sin(f / 30 + i * 1.7) * 40;
      const y = yMin + rnd(seed + i + 6) * (yMax - yMin) + Math.cos(f / 26 + i) * 30;
      const a = 0.4 + 0.6 * Math.abs(Math.sin(f / 22 + i));
      return (
        <g key={i} opacity={a}>
          <circle cx={x} cy={y} r={r * 3} fill={color} opacity={0.25} />
          <circle cx={x} cy={y} r={r} fill={color} />
        </g>
      );
    })}
  </g>
);

/** Animated wave band (ocean surface, lakes). */
export const Waves: React.FC<{ y: number; f: number; color: string; crest?: string; amp?: number; speed?: number; outline?: boolean }> = ({
  y, f, color, crest = "#FFFFFF", amp = 14, speed = 1, outline = true,
}) => {
  const pts: string[] = [];
  const n = 120;
  for (let i = 0; i <= n; i++) {
    const x = X0 + (i / n) * WW;
    const yy = y + amp * Math.sin(i * 0.55 + f * 0.05 * speed) + amp * 0.4 * Math.sin(i * 1.3 - f * 0.03 * speed);
    pts.push(`${x.toFixed(1)} ${yy.toFixed(1)}`);
  }
  const top = "M" + pts.join(" L");
  return (
    <g>
      <path d={`${top} L${X0 + WW} ${Y0 + HH} L${X0} ${Y0 + HH}Z`} fill={color} />
      {outline && <path d={top} fill="none" {...ol()} />}
      <path d={top} fill="none" stroke={crest} strokeWidth={5} strokeDasharray="40 70" strokeDashoffset={-f * speed} opacity={0.8} transform="translate(0 14)" />
    </g>
  );
};

/** Seaweed that sways (underwater). */
export const Seaweed: React.FC<{ x: number; y: number; h: number; f: number; color?: string; seed?: number }> = ({
  x, y, h, f, color = "#3FA06A", seed = 0,
}) => {
  const seg = 6;
  const pts: string[] = [];
  for (let i = 0; i <= seg; i++) {
    const k = i / seg;
    pts.push(`${(x + Math.sin(f / 22 + seed + k * 3) * 26 * k).toFixed(1)} ${(y - h * k).toFixed(1)}`);
  }
  return <path d={"M" + pts.join(" L")} fill="none" stroke={color} strokeWidth={20} strokeLinecap="round" strokeLinejoin="round" />;
};

/** Little fish swimming across (wraps around the layer). */
export const Fish: React.FC<{ f: number; n: number; seed?: number; yMin: number; yMax: number }> = ({ f, n, seed = 71, yMin, yMax }) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const dir = rnd(seed + i) > 0.5 ? 1 : -1;
      const speed = 1.2 + rnd(seed + i + 2) * 1.6;
      const x = X0 + ((rnd(seed + i + 4) * WW + dir * f * speed) % WW + WW) % WW;
      const y = yMin + rnd(seed + i + 6) * (yMax - yMin) + Math.sin(f / 14 + i) * 10;
      const color = [R.shoe, R.glow, "#7FD3E8", R.flower][i % 4];
      return (
        <g key={i} transform={`translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${dir} 1)`}>
          <path d="M-34 0 L-52 -16 L-52 16Z" fill={color} {...ol(3)} />
          <ellipse cx={0} cy={0} rx={36} ry={20} fill={color} {...ol(3)} />
          <circle cx={18} cy={-4} r={4} fill={INK} />
        </g>
      );
    })}
  </g>
);

/** Simple outlined building block with windows (city skylines). */
export const Building: React.FC<{ x: number; y: number; w: number; h: number; color: string; lit?: boolean; seed?: number }> = ({
  x, y, w, h, color, lit = false, seed = 0,
}) => (
  <g>
    <rect x={x} y={y - h} width={w} height={h + 400} fill={color} {...ol()} />
    {Array.from({ length: Math.floor((h - 40) / 70) }, (_, r) =>
      Array.from({ length: Math.max(1, Math.floor((w - 30) / 60)) }, (__, c) => (
        <rect key={`${r}-${c}`} x={x + 22 + c * 60} y={y - h + 30 + r * 70} width={30} height={40} rx={4}
          fill={lit && rnd(seed + r * 7 + c) > 0.45 ? R.glow : "#CFE3F5"} {...ol(3)} />
      )))}
  </g>
);
