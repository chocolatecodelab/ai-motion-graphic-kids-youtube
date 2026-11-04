// Placeholder vector environments (until the M2 SVG scene library exists).
// Each theme has 3 parallax layers drawn in world coordinates that extend well past
// the frame, so wide shots, pans and zoom-outs never show an edge.
import React from "react";
import { C } from "../brand";
import type { Theme } from "../types";
import { H, W } from "./layout";

export type Layer = "far" | "mid" | "near";
export const LAYER_PARALLAX: Record<Layer, number> = { far: 0.35, mid: 0.7, near: 1 };

const X0 = -W, Y0 = -0.6 * H, WW = 3 * W, HH = 2.2 * H;

const Svg: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <svg viewBox={`${X0} ${Y0} ${WW} ${HH}`} width={WW} height={HH}
    style={{ position: "absolute", left: X0, top: Y0, overflow: "visible" }}>
    {children}
  </svg>
);

const rand = (i: number) => {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};

const Clouds: React.FC<{ f: number; y: number; n: number; color?: string; speed?: number }> = ({ f, y, n, color = C.white, speed = 0.4 }) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const x = X0 + ((rand(i) * WW + f * speed * (0.5 + rand(i + 9))) % WW);
      const s = 0.6 + rand(i + 3) * 0.9;
      return (
        <g key={i} transform={`translate(${x} ${y + rand(i + 5) * 260}) scale(${s})`} opacity={0.92}>
          <ellipse cx={0} cy={0} rx={130} ry={46} fill={color} />
          <ellipse cx={-60} cy={10} rx={70} ry={38} fill={color} />
          <ellipse cx={70} cy={8} rx={80} ry={40} fill={color} />
          <ellipse cx={10} cy={-30} rx={70} ry={45} fill={color} />
        </g>
      );
    })}
  </g>
);

const Dots: React.FC<{ f: number; n: number; seed: number; r: number; colors: string[] }> = ({ f, n, seed, r, colors }) => (
  <g>
    {Array.from({ length: n }, (_, i) => {
      const k = i + seed;
      const x = X0 + rand(k) * WW + Math.sin(f / 13 + k) * 14;
      const y = Y0 + rand(k + 7) * HH + Math.cos(f / 11 + k) * 12;
      return <circle key={i} cx={x} cy={y} r={r * (0.6 + rand(k + 2))} fill={colors[i % colors.length]} opacity={0.85} />;
    })}
  </g>
);

const Window: React.FC<{ x: number; y: number; r: number; f: number }> = ({ x, y, r, f }) => (
  <g>
    <circle cx={x} cy={y} r={r + 26} fill="#6B4423" />
    <clipPath id="win"><circle cx={x} cy={y} r={r} /></clipPath>
    <g clipPath="url(#win)">
      <rect x={x - r} y={y - r} width={2 * r} height={2 * r} fill="#5DA9E9" />
      <rect x={x - r} y={y - r * 0.2} width={2 * r} height={r * 1.2} fill="#8CC7F2" />
      <g transform={`translate(${x - 2000} ${y - 60})`}><Clouds f={f} y={0} n={10} speed={0.25} /></g>
    </g>
    <path d={`M${x - r} ${y} H${x + r} M${x} ${y - r} V${y + r}`} stroke="#6B4423" strokeWidth={16} />
  </g>
);

const attic = (layer: Layer, f: number, bench = false) => {
  if (layer === "far") return (
    <Svg>
      <defs>
        <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#B57B45" /><stop offset="1" stopColor="#8E5A2E" />
        </linearGradient>
      </defs>
      <rect x={X0} y={Y0} width={WW} height={HH} fill="url(#wall)" />
      {Array.from({ length: 40 }, (_, i) => (
        <rect key={i} x={X0 + i * 150} y={Y0} width={4} height={HH} fill="#7A4A22" opacity={0.35} />
      ))}
      {/* sloped roof beams */}
      <path d={`M${X0} ${0.15 * H} L${W / 2} ${-0.45 * H} L${X0 + WW} ${0.15 * H}`} stroke="#5C3A1E" strokeWidth={70} fill="none" />
      <path d={`M${-0.2 * W} ${0.55 * H} L${W / 2} ${-0.1 * H} L${1.2 * W} ${0.55 * H}`} stroke="#6B4423" strokeWidth={34} fill="none" opacity={0.8} />
      <Window x={0.68 * W} y={0.32 * H} r={160} f={f} />
      {/* sunbeam from the window */}
      <path d={`M${0.6 * W} ${0.4 * H} L${0.25 * W} ${1.02 * H} L${0.62 * W} ${1.02 * H} L${0.74 * W} ${0.42 * H} Z`} fill="#FFF1C1" opacity={0.18} />
    </Svg>
  );
  if (layer === "mid") return (
    <Svg>
      {/* shelves with boxes and half-built gadgets */}
      <rect x={-0.55 * W} y={0.28 * H} width={0.55 * W} height={18} fill="#5C3A1E" />
      <rect x={-0.5 * W} y={0.16 * H} width={160} height={110} rx={8} fill="#D9A066" />
      <rect x={-0.24 * W} y={0.12 * H} width={120} height={150} rx={8} fill={C.teal} opacity={0.85} />
      <circle cx={1.25 * W} cy={0.2 * H} r={70} fill={C.brass} />
      <rect x={1.08 * W} y={0.28 * H} width={0.5 * W} height={18} fill="#5C3A1E" />
      {bench && (
        <g>
          <rect x={0.18 * W} y={0.7 * H} width={0.64 * W} height={36} rx={8} fill="#7A4E2D" />
          <rect x={0.22 * W} y={0.73 * H} width={30} height={0.25 * H} fill="#5C3A1E" />
          <rect x={0.76 * W} y={0.73 * H} width={30} height={0.25 * H} fill="#5C3A1E" />
          <rect x={0.3 * W} y={0.64 * H} width={120} height={50} rx={6} fill={C.orange} />
          <circle cx={0.58 * W} cy={0.66 * H} r={34} fill={C.brass} />
          <rect x={0.66 * W} y={0.6 * H} width={14} height={80} rx={4} fill="#9AA5B1" />
        </g>
      )}
    </Svg>
  );
  return (
    <Svg>
      <rect x={X0} y={0.93 * H} width={WW} height={HH} fill="#7A4E2D" />
      {Array.from({ length: 30 }, (_, i) => (
        <rect key={i} x={X0 + i * 200} y={0.93 * H} width={6} height={0.6 * H} fill="#5C3A1E" opacity={0.5} />
      ))}
      <ellipse cx={0.45 * W} cy={1.0 * H} rx={260} ry={40} fill="#FFF1C1" opacity={bench ? 0.35 : 0.18} />
      <rect x={-0.35 * W} y={0.72 * H} width={260} height={200} rx={10} fill="#C98A50" />
      <rect x={1.12 * W} y={0.78 * H} width={200} height={150} rx={10} fill="#D9A066" />
    </Svg>
  );
};

const sunbeam = (layer: Layer, f: number) => {
  const colors = ["#FF5A5A", C.orange, C.yellow, "#5BCB6B", "#3D8BFF", "#8B5CF6"];
  if (layer === "far") return (
    <Svg>
      <defs>
        <linearGradient id="sb" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0F1E45" /><stop offset="1" stopColor={C.blue} />
        </linearGradient>
      </defs>
      <rect x={X0} y={Y0} width={WW} height={HH} fill="url(#sb)" />
      <Dots f={f} n={140} seed={3} r={3} colors={["#FFFFFF", "#CFE3FF"]} />
    </Svg>
  );
  if (layer === "mid") return (
    <Svg>
      <path d={`M${X0} ${0.1 * H} L${X0 + WW} ${0.35 * H} L${X0 + WW} ${0.75 * H} L${X0} ${0.5 * H} Z`} fill="#FFFFFF" opacity={0.16} />
      {colors.map((c, i) => (
        <path key={c} d={`M${-0.3 * W} ${0.42 * H} C ${0.4 * W} ${0.42 * H + Math.sin(f / 20 + i) * 30}, ${1.0 * W} ${(0.2 + i * 0.12) * H}, ${2 * W} ${(0.05 + i * 0.16) * H}`}
          stroke={c} strokeWidth={34} fill="none" opacity={0.75} strokeLinecap="round" />
      ))}
    </Svg>
  );
  return <Svg><Dots f={f} n={60} seed={50} r={6} colors={["#FFFFFF", C.yellow]} /></Svg>;
};

const sky = (layer: Layer, f: number) => {
  if (layer === "far") return (
    <Svg>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3D7FD6" /><stop offset="1" stopColor="#BFE3FF" />
        </linearGradient>
      </defs>
      <rect x={X0} y={Y0} width={WW} height={HH} fill="url(#sky)" />
    </Svg>
  );
  if (layer === "mid") return <Svg><Clouds f={f} y={-0.2 * H} n={14} /></Svg>;
  return (
    <Svg>
      {Array.from({ length: 16 }, (_, i) => {
        const x = X0 + i * 380;
        const h = 120 + rand(i) * 120;
        return (
          <g key={i}>
            <rect x={x} y={1.2 * H - h} width={260} height={h + 400} fill={i % 2 ? "#E8D6C0" : "#F4F0E8"} />
            <path d={`M${x - 20} ${1.2 * H - h} L${x + 130} ${1.2 * H - h - 90} L${x + 280} ${1.2 * H - h} Z`} fill={C.orange} />
          </g>
        );
      })}
    </Svg>
  );
};

const air = (layer: Layer, f: number) => {
  if (layer === "far") return (
    <Svg>
      <defs>
        <linearGradient id="air" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2E5DA8" /><stop offset="1" stopColor="#7FB7E6" />
        </linearGradient>
      </defs>
      <rect x={X0} y={Y0} width={WW} height={HH} fill="url(#air)" />
      <Dots f={f} n={180} seed={1} r={5} colors={["#DCEBFA", "#B9D8F2"]} />
    </Svg>
  );
  if (layer === "mid") return <Svg><Dots f={f} n={90} seed={20} r={10} colors={[C.cream, "#CFE8E2"]} /></Svg>;
  return <Svg><Dots f={f} n={26} seed={70} r={18} colors={[C.cream, C.teal]} /></Svg>;
};

const sunset = (layer: Layer, f: number) => {
  if (layer === "far") return (
    <Svg>
      <defs>
        <linearGradient id="ss" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3B4E8C" /><stop offset="0.45" stopColor={C.orange} />
          <stop offset="0.7" stopColor={C.yellow} /><stop offset="1" stopColor="#FBE3B0" />
        </linearGradient>
      </defs>
      <rect x={X0} y={Y0} width={WW} height={HH} fill="url(#ss)" />
      <circle cx={0.7 * W} cy={0.66 * H} r={110} fill="#FFE9A8" />
      <circle cx={0.7 * W} cy={0.66 * H} r={170} fill="#FFE9A8" opacity={0.25} />
    </Svg>
  );
  if (layer === "mid") return (
    <Svg>
      <Clouds f={f} y={-0.1 * H} n={8} color="#F7A9A0" speed={0.2} />
      <path d={`M${X0} ${0.8 * H} Q${0} ${0.62 * H} ${0.5 * W} ${0.78 * H} T${1.5 * W} ${0.74 * H} T${X0 + WW} ${0.8 * H} V${Y0 + HH} H${X0} Z`} fill="#6A4A7A" />
    </Svg>
  );
  return (
    <Svg>
      <path d={`M${X0} ${0.95 * H} Q${0.3 * W} ${0.86 * H} ${0.7 * W} ${0.94 * H} T${X0 + WW} ${0.92 * H} V${Y0 + HH} H${X0} Z`} fill="#3E6B4E" />
    </Svg>
  );
};

const mars = (layer: Layer) => {
  if (layer === "far") return (
    <Svg>
      <defs>
        <linearGradient id="mars" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#B85A2E" /><stop offset="1" stopColor="#F2A766" />
        </linearGradient>
        <radialGradient id="halo"><stop offset="0" stopColor="#B9C6D6" stopOpacity={0.9} /><stop offset="1" stopColor="#B9C6D6" stopOpacity={0} /></radialGradient>
      </defs>
      <rect x={X0} y={Y0} width={WW} height={HH} fill="url(#mars)" />
      <circle cx={0.28 * W} cy={0.62 * H} r={150} fill="url(#halo)" />
      <circle cx={0.28 * W} cy={0.62 * H} r={30} fill="#FFF6E0" />
    </Svg>
  );
  if (layer === "mid") return (
    <Svg>
      <path d={`M${X0} ${0.8 * H} L${-0.2 * W} ${0.62 * H} L${0.1 * W} ${0.62 * H} L${0.25 * W} ${0.78 * H} L${0.9 * W} ${0.7 * H} L${1.05 * W} ${0.58 * H} L${1.4 * W} ${0.58 * H} L${1.6 * W} ${0.8 * H} L${X0 + WW} ${0.8 * H} V${Y0 + HH} H${X0} Z`} fill="#A8452A" />
    </Svg>
  );
  return (
    <Svg>
      <rect x={X0} y={0.9 * H} width={WW} height={HH} fill="#B5532E" />
      {Array.from({ length: 24 }, (_, i) => (
        <ellipse key={i} cx={X0 + rand(i) * WW} cy={0.95 * H + rand(i + 4) * 0.3 * H} rx={30 + rand(i + 1) * 70} ry={18 + rand(i + 2) * 30} fill="#8C3B22" />
      ))}
    </Svg>
  );
};

const space = (layer: Layer, f: number) =>
  layer === "far" ? (
    <Svg><rect x={X0} y={Y0} width={WW} height={HH} fill="#0B1533" /><Dots f={f * 0.2} n={260} seed={9} r={2.5} colors={["#FFFFFF", "#CFE3FF", C.yellow]} /></Svg>
  ) : layer === "mid" ? (
    <Svg><circle cx={1.2 * W} cy={0.2 * H} r={220} fill={C.orange} /><circle cx={1.15 * W} cy={0.15 * H} r={220} fill="#0B1533" opacity={0.35} /></Svg>
  ) : <Svg>{null}</Svg>;

const studio = (layer: Layer) =>
  layer === "far" ? (
    <Svg>
      <rect x={X0} y={Y0} width={WW} height={HH} fill={C.cream} />
      <circle cx={0.15 * W} cy={0.2 * H} r={260} fill={C.teal} opacity={0.25} />
      <circle cx={0.9 * W} cy={0.8 * H} r={320} fill={C.yellow} opacity={0.3} />
    </Svg>
  ) : layer === "near" ? (
    <Svg><rect x={X0} y={0.94 * H} width={WW} height={HH} fill="#E6DDCC" /></Svg>
  ) : <Svg>{null}</Svg>;

export const BackgroundLayer: React.FC<{ theme: Theme; layer: Layer; frame: number }> = ({ theme, layer, frame }) => {
  switch (theme) {
    case "attic": return attic(layer, frame);
    case "workbench": return attic(layer, frame, true);
    case "sunbeam": return sunbeam(layer, frame);
    case "sky": return sky(layer, frame);
    case "air": return air(layer, frame);
    case "sunset": return sunset(layer, frame);
    case "mars": return mars(layer);
    case "space": return space(layer, frame);
    default: return studio(layer);
  }
};
