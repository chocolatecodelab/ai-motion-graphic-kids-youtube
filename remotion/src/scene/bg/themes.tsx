// M2 SVG scene library: 22 environments in the Arka & Lipa style, each in 3 parallax layers
// (far / mid / near). Characters stand on the ground line at about y = 0.92 H.
import React from "react";
import { C as R } from "../../rig/palette";
import { Topo } from "../../rig/Topo";
import { H, W } from "../layout";
import {
  Backdrop, Building, Bubbles, Bush, Clouds, Fall, Fish, Ground, HH, Hills, INK, Layer, Motes,
  Mountains, ol, OUT, Pine, rnd, Rock, Seaweed, Stars, Sun, Tree, Tufts, Waves, WW, X0, Y0,
} from "./kit";

export type BgLayer = "far" | "mid" | "near";
type ThemeFn = (layer: BgLayer, f: number) => React.ReactElement;
const GY = 0.93 * H; // ground line

/* ------------------------------------------------------------- indoor: attic / workbench */

const RoundWindow: React.FC<{ x: number; y: number; r: number; f: number; night?: boolean }> = ({ x, y, r, f, night }) => (
  <g>
    <circle cx={x} cy={y} r={r + 30} fill={R.packDark} {...ol()} />
    <clipPath id="bg-win"><circle cx={x} cy={y} r={r} /></clipPath>
    <g clipPath="url(#bg-win)">
      <rect x={x - r} y={y - r} width={2 * r} height={2 * r} fill={night ? R.navyDeep : "#7EC0F0"} />
      <rect x={x - r} y={y + r * 0.1} width={2 * r} height={r} fill={night ? R.navy : "#B5DDF8"} />
      {!night && <g transform={`translate(${x - 1400} ${y - 40}) scale(0.6)`}><Clouds f={f} y={0} n={8} spread={60} speed={0.2} /></g>}
    </g>
    <circle cx={x} cy={y} r={r} fill="none" {...ol()} />
    <path d={`M${x - r} ${y} H${x + r} M${x} ${y - r} V${y + r}`} stroke={R.packDark} strokeWidth={18} />
    <path d={`M${x - r} ${y} H${x + r} M${x} ${y - r} V${y + r}`} fill="none" {...ol(3)} />
  </g>
);

const attic = (bench: boolean): ThemeFn => (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-attic" stops={[[0, "#C98E57"], [1, "#9A6438"]]} />
      {Array.from({ length: 30 }, (_, i) => (
        <path key={i} d={`M${X0 + i * 190} ${Y0} V${Y0 + HH}`} stroke="#7E4F2A" strokeWidth={4} opacity={0.35} />
      ))}
      <path d={`M${X0} ${0.2 * H} L${W / 2} ${-0.42 * H} L${X0 + WW} ${0.2 * H}`} fill="none" stroke={R.packDark} strokeWidth={70} />
      <path d={`M${X0} ${0.2 * H} L${W / 2} ${-0.42 * H} L${X0 + WW} ${0.2 * H}`} fill="none" {...ol()} transform="translate(0 36)" />
      <RoundWindow x={0.68 * W} y={0.3 * H} r={150} f={f} />
      <path d={`M${0.6 * W} ${0.38 * H} L${0.28 * W} ${GY + 20} L${0.62 * W} ${GY + 20} L${0.75 * W} ${0.4 * H}Z`} fill="#FFF1C1" opacity={0.2} />
      <Motes f={f} n={26} seed={4} color="#FFF4D0" r={2.5} yMin={0.35 * H} yMax={0.9 * H} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      {/* shelves: a pinned map, books, a globe and boxes */}
      <g transform={`translate(${0.6 * W} 0)`}>
      <rect x={-0.62 * W} y={0.3 * H} width={0.6 * W} height={22} fill={R.packDark} {...ol()} />
      <rect x={-0.56 * W} y={0.12 * H} width={150} height={0.18 * H} rx={6} fill={R.paper} {...ol()} />
      <path d={`M${-0.55 * W} ${0.2 * H} C${-0.5 * W} ${0.15 * H} ${-0.5 * W} ${0.26 * H} ${-0.49 * W} ${0.2 * H}`} fill="none" stroke={R.water} strokeWidth={5} />
      <path d={`M${-0.54 * W} ${0.27 * H} L${-0.5 * W} ${0.16 * H}`} stroke={R.route} strokeWidth={4} strokeDasharray="8 8" />
      {[0, 1, 2, 3].map((i) => (
        <rect key={i} x={-0.44 * W + i * 34} y={0.3 * H - 110 - (i % 2) * 14} width={30} height={110 + (i % 2) * 14} rx={4}
          fill={[R.shoe, R.scarf, R.bedroll, R.brass][i]} {...ol(3.5)} />
      ))}
      <circle cx={-0.18 * W} cy={0.3 * H - 70} r={60} fill={R.water} {...ol()} />
      <path d={`M${-0.18 * W - 40} ${0.3 * H - 90} C${-0.18 * W} ${0.3 * H - 60} ${-0.18 * W - 10} ${0.3 * H - 40} ${-0.18 * W + 30} ${0.3 * H - 30}`} fill="none" stroke={R.land} strokeWidth={14} strokeLinecap="round" />
      </g>
      <rect x={1.06 * W} y={0.32 * H} width={0.55 * W} height={22} fill={R.packDark} {...ol()} />
      <rect x={1.12 * W} y={0.32 * H - 120} width={160} height={120} rx={8} fill={R.paperMid} {...ol()} />
      <rect x={1.24 * W} y={0.32 * H - 90} width={120} height={90} rx={8} fill={R.paperDark} {...ol()} />
      {bench && (
        <g>
          <rect x={0.16 * W} y={0.68 * H} width={0.68 * W} height={40} rx={8} fill={R.pack} {...ol()} />
          <rect x={0.2 * W} y={0.68 * H + 40} width={30} height={0.25 * H} fill={R.packDark} {...ol()} />
          <rect x={0.78 * W} y={0.68 * H + 40} width={30} height={0.25 * H} fill={R.packDark} {...ol()} />
          {/* desk lamp with a warm pool of light */}
          <ellipse cx={0.36 * W} cy={0.68 * H} rx={180} ry={30} fill={R.glow} opacity={0.35} />
          <path d={`M${0.3 * W} ${0.68 * H} L${0.32 * W} ${0.52 * H} L${0.38 * W} ${0.47 * H}`} fill="none" {...ol(12)} />
          <path d={`M${0.36 * W} ${0.44 * H} L${0.42 * W} ${0.46 * H} L${0.4 * W} ${0.52 * H} L${0.34 * W} ${0.5 * H}Z`} fill={R.shoe} {...ol()} />
          {/* gears and a brass compass in pieces */}
          <circle cx={0.56 * W} cy={0.66 * H} r={34} fill={R.brass} {...ol()} />
          <circle cx={0.56 * W} cy={0.66 * H} r={12} fill={R.brassDark} {...ol(3)} />
          <rect x={0.64 * W} y={0.6 * H} width={16} height={70} rx={5} fill="#9AA5B1" {...ol(3.5)} />
          <rect x={0.7 * W} y={0.63 * H} width={90} height={40} rx={6} fill={R.paper} {...ol(3.5)} />
        </g>
      )}
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color={R.pack} shade={R.packDark} />
      {Array.from({ length: 26 }, (_, i) => (
        <path key={i} d={`M${X0 + i * 230} ${GY} V${GY + 0.6 * H}`} stroke={R.packDark} strokeWidth={4} opacity={0.5} />
      ))}
      <ellipse cx={0.45 * W} cy={GY + 50} rx={300} ry={44} fill="#FFF1C1" opacity={0.22} />
      <rect x={-0.1 * W} y={GY - 210} width={280} height={210} rx={10} fill={R.packLight} {...ol()} />
      <path d={`M${-0.1 * W} ${GY - 150} H${-0.1 * W + 280}`} {...ol(4)} />
      <rect x={0.94 * W} y={GY - 150} width={210} height={150} rx={10} fill={R.paperMid} {...ol()} />
    </Layer>
  );
};

/* ------------------------------------------------------------- sky, sunbeam, air, sunset */

const sky: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-sky" stops={[[0, "#4C8FE0"], [0.7, "#A9D6FA"], [1, "#DDF0FF"]]} />
      <Sun x={0.82 * W} y={0.12 * H} r={70} f={f} />
      <Hills y={0.9 * H} amp={160} color="#9FD08A" shade="#6FAF62" seed={2} />
    </Layer>
  );
  if (layer === "mid") return <Layer><Clouds f={f} y={-0.25 * H} n={14} spread={380} /></Layer>;
  return (
    <Layer>
      <Ground y={GY} color={R.land} shade={R.leafDark} amp={10} seed={4} />
      <Tufts y={GY + 10} n={40} f={f} />
      <Tree x={0.04 * W} y={GY + 20} s={1.1} f={f} />
      <Tree x={0.95 * W} y={GY + 20} s={0.9} f={f} seed={2} />
    </Layer>
  );
};

const sunbeam: ThemeFn = (layer, f) => {
  const colors = ["#FF5A5A", R.shoe, R.glow, "#5BCB6B", "#3D8BFF", "#8B5CF6"];
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-beam" stops={[[0, R.navyDeep], [1, "#34508F"]]} />
      <Stars f={f} n={150} seed={3} yMax={1.6 * H} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      <path d={`M${X0} ${0.1 * H} L${X0 + WW} ${0.32 * H} L${X0 + WW} ${0.78 * H} L${X0} ${0.52 * H}Z`} fill="#FFFFFF" opacity={0.14} />
      {colors.map((c, i) => (
        <path key={c} d={`M${-0.4 * W} ${0.44 * H} C${0.4 * W} ${0.44 * H + Math.sin(f / 20 + i) * 34} ${1.0 * W} ${(0.2 + i * 0.12) * H} ${2.1 * W} ${(0.04 + i * 0.16) * H}`}
          stroke={c} strokeWidth={36} fill="none" opacity={0.8} strokeLinecap="round" />
      ))}
    </Layer>
  );
  return <Layer><Motes f={f} n={50} seed={50} color="#FFFFFF" r={4} /></Layer>;
};

const air: ThemeFn = (layer, f) => {
  const molecule = (i: number, seed: number, r: number, colors: string[]) => {
    const k = i + seed;
    const x = X0 + rnd(k) * WW + Math.sin(f / 13 + k) * 16;
    const y = Y0 + rnd(k + 7) * HH + Math.cos(f / 11 + k) * 14;
    const two = rnd(k + 3) > 0.5; // N2 / O2 pairs
    const c = colors[i % colors.length];
    return (
      <g key={i} transform={`translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${(f * 0.6 + k * 40) % 360})`}>
        <circle cx={two ? -r * 0.6 : 0} r={r} fill={c} {...ol(3)} />
        {two && <circle cx={r * 0.6} r={r} fill={c} {...ol(3)} />}
      </g>
    );
  };
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-air" stops={[[0, "#3A6CB8"], [1, "#8CC2EC"]]} />
      {Array.from({ length: 120 }, (_, i) => molecule(i, 1, 5, ["#DCEBFA", "#B9D8F2"]))}
    </Layer>
  );
  if (layer === "mid") return <Layer>{Array.from({ length: 60 }, (_, i) => molecule(i, 20, 11, ["#F4F8FF", "#CFE8E2"]))}</Layer>;
  return <Layer>{Array.from({ length: 18 }, (_, i) => molecule(i, 70, 20, [R.hat, R.scarfLight]))}</Layer>;
};

const sunset: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-sunset" stops={[[0, "#3B4E8C"], [0.42, "#E8735A"], [0.7, "#FFC46B"], [1, "#FBE3B0"]]} />
      <Sun x={0.7 * W} y={0.66 * H} r={110} f={f} color="#FFE3A0" rays={false} />
      <Clouds f={f} y={0.05 * H} n={7} spread={200} tint="#F7B6A0" shade="#E88E86" speed={0.15} />
    </Layer>
  );
  if (layer === "mid") return <Layer><Hills y={0.82 * H} amp={140} color="#7A5A8C" shade="#5A3F70" seed={8} /></Layer>;
  return (
    <Layer>
      <Ground y={GY} color="#4E7A55" shade="#36593D" amp={12} seed={6} />
      <Pine x={0.05 * W} y={GY + 10} s={0.9} f={f} color="#2F5A45" shade="#1F4232" />
      <Pine x={0.94 * W} y={GY + 10} s={1.1} f={f} color="#2F5A45" shade="#1F4232" seed={3} />
    </Layer>
  );
};

/* ------------------------------------------------------------- planets */

const mars: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-mars" stops={[[0, "#B85A2E"], [1, "#F2A766"]]} />
      <defs><radialGradient id="bg-halo"><stop offset="0" stopColor="#B9C6D6" stopOpacity={0.9} /><stop offset="1" stopColor="#B9C6D6" stopOpacity={0} /></radialGradient></defs>
      <circle cx={0.28 * W} cy={0.6 * H} r={160} fill="url(#bg-halo)" />
      <circle cx={0.28 * W} cy={0.6 * H} r={30} fill="#FFF6E0" {...ol(3)} />
      <Mountains base={0.82 * H} height={240} color="#C4643A" shade="#93442A" seed={4} n={6} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      <Hills y={0.88 * H} amp={90} color="#A8452A" shade="#7E3020" seed={12} />
      <Motes f={f} n={30} seed={8} color="#F6C08C" r={2.5} />
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#B5532E" shade="#8C3B22" amp={8} />
      {Array.from({ length: 18 }, (_, i) => <Rock key={i} x={X0 + rnd(i) * WW} y={GY + 30 + rnd(i + 4) * 0.25 * H} s={0.4 + rnd(i + 1) * 0.6} color="#9C4A2C" shade="#74321D" />)}
    </Layer>
  );
};

const space: ThemeFn = (layer, f) => {
  if (layer === "far") return <Layer><Backdrop id="bg-space" stops={[[0, "#0B1533"], [1, "#1C2858"]]} /><Stars f={f} n={240} seed={9} yMax={Y0 + HH} /></Layer>;
  if (layer === "mid") return (
    <Layer>
      <g transform={`translate(${0.86 * W} ${0.24 * H}) scale(0.62)`}>
        <circle r={220} fill={R.shoe} {...ol()} />
        <path d="M-220 0 A220 220 0 0 0 220 0 A220 120 0 0 1 -220 0Z" fill={R.shoeDark} opacity={0.6} />
        <ellipse rx={340} ry={56} fill="none" stroke={R.brassLight} strokeWidth={16} transform="rotate(-14)" />
      </g>
      <circle cx={0.1 * W} cy={0.72 * H} r={90} fill={R.water} {...ol()} />
      <path d={`M${0.1 * W - 60} ${0.72 * H - 40} C${0.1 * W - 10} ${0.72 * H - 70} ${0.1 * W + 10} ${0.72 * H} ${0.1 * W + 60} ${0.72 * H + 20}`} fill="none" stroke={R.land} strokeWidth={22} strokeLinecap="round" />
    </Layer>
  );
  return <Layer><Motes f={f} n={14} seed={90} color="#CFE3FF" r={3} /></Layer>;
};

/* ------------------------------------------------------------- nature */

const forest: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-forest" stops={[[0, "#8FC9E8"], [1, "#DDEFD8"]]} />
      <Hills y={0.7 * H} amp={150} color="#8DBF8A" shade="#6A9E6A" seed={3} />
      {Array.from({ length: 16 }, (_, i) => <Pine key={i} x={X0 + i * (WW / 16) + rnd(i) * 80} y={0.72 * H} s={0.45 + rnd(i + 2) * 0.2} f={f} color="#5E9E72" shade="#4A8360" seed={i} />)}
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      {Array.from({ length: 9 }, (_, i) => <Pine key={i} x={X0 + i * (WW / 9) + rnd(i + 5) * 120} y={0.86 * H} s={0.8 + rnd(i + 7) * 0.3} f={f} seed={i + 3} />)}
      <Fall f={f} n={16} kind="leaf" speed={1.2} />
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#7FB069" shade="#5C8F4C" amp={10} seed={2} />
      <Tufts y={GY + 10} n={46} f={f} />
      <Tree x={0.03 * W} y={GY + 20} s={1.2} f={f} />
      <Bush x={0.17 * W} y={GY + 30} s={0.8} berries />
      <Rock x={0.85 * W} y={GY + 40} s={0.7} />
      <Tree x={0.97 * W} y={GY + 20} s={1.1} f={f} seed={4} />
    </Layer>
  );
};

const jungle: ThemeFn = (layer, f) => {
  const leaf = (x: number, y: number, s: number, rot: number, c: string, i: number) => (
    <g key={i} transform={`translate(${x} ${y}) rotate(${rot + Math.sin(f / 30 + i) * 3}) scale(${s})`}>
      <path d="M0 0 C40 -40 140 -50 220 0 C140 50 40 40 0 0Z" fill={c} {...ol(OUT / s)} />
      <path d="M0 0 L210 0" stroke={R.leafDark} strokeWidth={4 / s} />
    </g>
  );
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-jungle" stops={[[0, "#9ED8C4"], [1, "#E4F5DA"]]} />
      <Hills y={0.75 * H} amp={200} color="#6FB58A" shade="#4E946A" seed={9} bumps={7} />
      <rect x={X0} y={0.45 * H} width={WW} height={0.3 * H} fill="#FFFFFF" opacity={0.25} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      {Array.from({ length: 10 }, (_, i) => {
        const x = X0 + i * (WW / 10) + rnd(i) * 100;
        return (
          <g key={i}>
            <path d={`M${x} ${GY} C${x - 20} ${0.5 * H} ${x + 20} ${0.2 * H} ${x} ${-0.3 * H}`} fill="none" stroke={R.packDark} strokeWidth={34} />
            <path d={`M${x + 60} ${-0.4 * H} Q${x + 70 + Math.sin(f / 40 + i) * 20} ${0.1 * H} ${x + 50} ${0.4 * H}`} fill="none" stroke={R.leafDark} strokeWidth={7} />
            {leaf(x, 0.05 * H, 0.9, -30, R.leaf, i)}
            {leaf(x, 0.15 * H, 0.8, 200, "#4FA35A", i + 20)}
          </g>
        );
      })}
      <Motes f={f} n={14} seed={30} color="#FFF6B0" r={3} yMin={0.3 * H} yMax={0.9 * H} />
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#5E9E5A" shade="#447A42" amp={8} seed={7} />
      {Array.from({ length: 14 }, (_, i) => leaf(X0 + rnd(i + 40) * WW, GY + 20, 0.7 + rnd(i) * 0.4, -150 + rnd(i + 2) * 120, i % 2 ? R.leaf : "#4FA35A", i + 60))}
      <Tufts y={GY + 20} n={30} f={f} flowers />
    </Layer>
  );
};

const ocean: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-ocean" stops={[[0, "#5BA8EE"], [0.75, "#BCE3FF"], [1, "#E8F6FF"]]} />
      <Sun x={0.2 * W} y={0.14 * H} r={64} f={f} />
      <Clouds f={f} y={-0.2 * H} n={9} spread={240} speed={0.2} />
    </Layer>
  );
  if (layer === "mid") return <Layer><Waves y={0.68 * H} f={f} color="#3F8FD6" amp={10} /><Waves y={0.78 * H} f={f} color="#2F78C2" amp={12} speed={1.4} /></Layer>;
  const palm = (x: number, s: number, i: number) => (
    <g key={i} transform={`translate(${x} ${GY + 30}) scale(${s})`}>
      <path d="M0 0 C10 -120 30 -240 60 -330" fill="none" stroke={R.pack} strokeWidth={30} strokeLinecap="round" />
      <path d="M0 0 C10 -120 30 -240 60 -330" fill="none" {...ol(OUT / s)} transform="translate(15 0)" opacity={0.4} />
      {[0, 60, 130, 200, 260].map((a, k) => (
        <path key={k} d="M0 0 C40 -30 120 -20 170 30 C110 0 50 0 0 0Z" fill={R.leaf} {...ol(OUT / s)}
          transform={`translate(60 -330) rotate(${a + Math.sin(f / 30 + k + i) * 4})`} />
      ))}
    </g>
  );
  return (
    <Layer>
      <Ground y={GY} color="#F2D9A6" shade="#DDBB7E" amp={6} seed={3} />
      {palm(0.0 * W, 1.1, 1)}
      {palm(0.88 * W, 0.95, 2)}
      {[[0.1, 0], [0.88, 1]].map(([px, k]) => (
        <path key={k} d="M0 0 C-8 -14 8 -24 18 -10 C28 -24 44 -14 36 0Z" transform={`translate(${px * W} ${GY + 70})`} fill={R.flower} {...ol(3)} />
      ))}
    </Layer>
  );
};

const underwater: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-under" stops={[[0, "#3FA6D9"], [0.6, "#1E6FA8"], [1, "#134B7A"]]} />
      {Array.from({ length: 7 }, (_, i) => (
        <path key={i} d={`M${X0 + i * 900 + Math.sin(f / 60 + i) * 60} ${Y0} L${X0 + i * 900 + 260} ${Y0} L${X0 + i * 900 + 700} ${1.2 * H} L${X0 + i * 900 + 300} ${1.2 * H}Z`}
          fill="#FFFFFF" opacity={0.07} />
      ))}
      <Fish f={f} n={8} seed={5} yMin={0.1 * H} yMax={0.5 * H} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      {Array.from({ length: 14 }, (_, i) => <Seaweed key={i} x={X0 + rnd(i + 3) * WW} y={GY + 40} h={220 + rnd(i) * 220} f={f} seed={i} color={i % 2 ? "#3FA06A" : "#2F8A5A"} />)}
      <Bubbles f={f} n={30} seed={7} />
    </Layer>
  );
  const coral = (x: number, c: string, i: number) => (
    <g key={i} transform={`translate(${x} ${GY + 40})`}>
      {[-40, 0, 40].map((dx, k) => (
        <path key={k} d={`M${dx} 0 C${dx - 10} -60 ${dx + 20} -90 ${dx + 6} -${130 + k * 20}`} fill="none" stroke={c} strokeWidth={22} strokeLinecap="round" />
      ))}
    </g>
  );
  return (
    <Layer>
      <Ground y={GY} color="#E8CF98" shade="#C9AE72" amp={10} seed={5} />
      {coral(0.04 * W, R.shoe, 1)}
      {coral(0.13 * W, R.flower, 2)}
      {coral(0.92 * W, "#F59FC0", 3)}
      <Rock x={0.8 * W} y={GY + 50} s={0.8} color="#7F8FA8" shade="#5E6C86" />
      <Fish f={f} n={3} seed={41} yMin={0.75 * H} yMax={0.85 * H} />
    </Layer>
  );
};

const desert: ThemeFn = (layer, f) => {
  const cactus = (x: number, s: number, i: number) => (
    <g key={i} transform={`translate(${x} ${GY + 30}) scale(${s})`}>
      <path d="M-22 0 L-22 -200 C-22 -230 22 -230 22 -200 L22 0Z" fill="#5FA368" {...ol(OUT / s)} />
      <path d="M-22 -110 L-60 -110 C-80 -110 -80 -150 -80 -170 C-80 -190 -56 -190 -56 -170 L-56 -136 L-22 -136" fill="#5FA368" {...ol(OUT / s)} />
      <path d="M22 -80 L56 -80 L56 -130 C56 -150 80 -150 80 -130 L80 -90 C80 -60 60 -56 22 -56" fill="#5FA368" {...ol(OUT / s)} />
      <circle cx={0} cy={-226} r={10} fill={R.flower} {...ol(3 / s)} />
    </g>
  );
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-desert" stops={[[0, "#6CB4F0"], [0.8, "#FBE2B4"], [1, "#FFEFD0"]]} />
      <Sun x={0.75 * W} y={0.15 * H} r={80} f={f} />
      <Mountains base={0.8 * H} height={220} color="#D99A63" shade="#B87A48" seed={21} n={6} />
    </Layer>
  );
  if (layer === "mid") return <Layer><Hills y={0.86 * H} amp={120} color="#EDC27F" shade="#D3A35E" seed={31} bumps={6} /></Layer>;
  return (
    <Layer>
      <Ground y={GY} color="#F4D28E" shade="#DDB26A" amp={14} seed={9} />
      {cactus(0.06 * W, 1, 1)}
      {cactus(0.92 * W, 0.8, 2)}
      <Rock x={0.2 * W} y={GY + 50} s={0.5} color="#C48A5A" shade="#9C6A40" />
    </Layer>
  );
};

const mountains: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-mount" stops={[[0, "#6FA9E6"], [1, "#D9ECFA"]]} />
      <Clouds f={f} y={-0.3 * H} n={6} spread={200} speed={0.15} />
      <Mountains base={0.78 * H} height={520} color="#8E9BC4" shade="#6B78A3" snow seed={2} n={6} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      <Hills y={0.86 * H} amp={140} color="#86B97C" shade="#5F955A" seed={13} />
      {Array.from({ length: 12 }, (_, i) => <Pine key={i} x={X0 + i * (WW / 12) + rnd(i + 8) * 100} y={0.84 * H} s={0.55} f={f} seed={i} />)}
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#9AAE7C" shade="#738B5A" amp={12} seed={12} />
      <Rock x={0.06 * W} y={GY + 40} s={1.2} />
      <Rock x={0.91 * W} y={GY + 30} s={0.9} />
      <Tufts y={GY + 10} n={26} f={f} flowers={false} />
    </Layer>
  );
};

const arctic: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-arctic" stops={[[0, "#1E3A6E"], [0.55, "#4E7FB8"], [1, "#BFD9F2"]]} />
      {[0, 1, 2].map((i) => (
        <path key={i} d={`M${X0} ${(0.05 + i * 0.07) * H} C${0} ${(-0.1 + i * 0.08) * H + Math.sin(f / 50 + i) * 30} ${W} ${(0.2 + i * 0.05) * H} ${X0 + WW} ${(0.02 + i * 0.06) * H}`}
          fill="none" stroke={["#62F2B6", "#7BD7F7", "#B48CF2"][i]} strokeWidth={60 - i * 14} opacity={0.35} strokeLinecap="round" />
      ))}
      <Stars f={f} n={60} seed={17} yMax={0.3 * H} />
      <Mountains base={0.8 * H} height={300} color="#E6F2FC" shade="#B8D2EA" seed={6} n={6} />
    </Layer>
  );
  if (layer === "mid") return <Layer><Hills y={0.88 * H} amp={90} color="#F4FAFF" shade="#C9DFF2" seed={22} /><Fall f={f} n={60} kind="snow" speed={1.5} /></Layer>;
  return (
    <Layer>
      <Ground y={GY} color="#FFFFFF" shade="#D6E7F5" amp={10} seed={14} />
      <g transform={`translate(${0.87 * W} ${GY + 20})`}>
        <path d="M-160 0 A160 150 0 0 1 160 0Z" fill="#F4FAFF" {...ol()} />
        <path d="M-50 0 A50 60 0 0 1 50 0Z" fill={R.navy} {...ol()} />
        {[-110, -40, 40, 110].map((x) => <path key={x} d={`M${x} 0 L${x * 0.8} -110`} {...ol(3)} opacity={0.5} />)}
      </g>
      <path d={`M${0.02 * W} ${GY + 40} L${0.11 * W} ${GY - 80} L${0.22 * W} ${GY + 40}Z`} fill="#CFE6F7" {...ol()} />
    </Layer>
  );
};

const volcano: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-volcano" stops={[[0, "#5A4A6E"], [0.6, "#E88A5A"], [1, "#F8C890"]]} />
      <g transform={`translate(${0.62 * W} ${0.8 * H})`}>
        <path d="M-520 0 L-120 -440 L120 -440 L520 0Z" fill="#6E5A6E" {...ol()} />
        <path d="M-120 -440 L120 -440 L60 -400 L-60 -410Z" fill="#FF7A3D" {...ol(4)} />
        <path d="M-60 -410 C-80 -300 -40 -200 -70 -80" fill="none" stroke="#FF8A3D" strokeWidth={22} strokeLinecap="round" />
        {Array.from({ length: 6 }, (_, i) => {
          const k = ((f * 0.6 + i * 40) % 240) / 240;
          return <circle key={i} cx={Math.sin(i * 2 + f / 40) * 40 * k} cy={-470 - k * 380} r={50 + k * 90} fill="#8C7C8C" opacity={0.5 * (1 - k)} {...ol(3)} />;
        })}
      </g>
    </Layer>
  );
  if (layer === "mid") return <Layer><Hills y={0.88 * H} amp={110} color="#7E6A6A" shade="#5E4C50" seed={27} /><Motes f={f} n={20} seed={13} color="#FFB060" r={3} /></Layer>;
  return (
    <Layer>
      <Ground y={GY} color="#6E5E5A" shade="#4E403E" amp={10} seed={18} />
      {Array.from({ length: 12 }, (_, i) => <Rock key={i} x={X0 + rnd(i + 9) * WW} y={GY + 40 + rnd(i) * 0.2 * H} s={0.4 + rnd(i + 3) * 0.5} color="#5A4A48" shade="#3E3230" />)}
    </Layer>
  );
};

const cave: ThemeFn = (layer, f) => {
  const crystal = (x: number, y: number, s: number, c: string, i: number) => {
    const glow = 0.4 + 0.3 * Math.sin(f / 25 + i);
    return (
      <g key={i} transform={`translate(${x} ${y}) scale(${s})`}>
        <circle r={70} fill={c} opacity={glow * 0.4} />
        <path d="M-20 0 L-12 -70 L0 -96 L12 -70 L20 0Z" fill={c} {...ol(OUT / s)} />
        <path d="M14 0 L30 -50 L40 -40 L36 0Z" fill={c} {...ol(OUT / s)} />
        <path d="M-6 -70 L0 -90 L4 -70Z" fill="#FFFFFF" opacity={0.6} />
      </g>
    );
  };
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-cave" stops={[[0, "#2A2440"], [1, "#4A3E62"]]} />
      {Array.from({ length: 22 }, (_, i) => {
        const x = X0 + i * (WW / 22);
        const h = 120 + rnd(i) * 260;
        return <path key={i} d={`M${x} ${Y0 + 0.5 * H} L${x + 50} ${Y0 + 0.5 * H + h} L${x + 100} ${Y0 + 0.5 * H}Z`} fill="#3E3456" {...ol()} />;
      })}
      <rect x={X0} y={Y0} width={WW} height={0.5 * H} fill="#3E3456" />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      <Hills y={0.9 * H} amp={160} color="#4A3E62" shade="#332A48" seed={33} bumps={7} />
      {crystal(0.12 * W, 0.86 * H, 0.9, "#7FD3E8", 1)}
      {crystal(0.85 * W, 0.84 * H, 0.7, "#B48CF2", 2)}
      <Motes f={f} n={18} seed={23} color="#9FE8F5" r={2.5} />
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#5A4C70" shade="#3E3456" amp={12} seed={21} />
      {crystal(0.05 * W, GY + 40, 1.3, "#7FD3E8", 3)}
      {crystal(0.93 * W, GY + 30, 1.1, R.glow, 4)}
      <Rock x={0.2 * W} y={GY + 50} s={0.8} color="#6E6086" shade="#4E4266" />
    </Layer>
  );
};

/* ------------------------------------------------------------- built places */

const city: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-city" stops={[[0, "#5C9EE6"], [1, "#CFE7FA"]]} />
      <Clouds f={f} y={-0.25 * H} n={8} spread={200} speed={0.2} />
      {Array.from({ length: 14 }, (_, i) => (
        <Building key={i} x={X0 + i * (WW / 14)} y={0.75 * H} w={WW / 14 - 20} h={260 + rnd(i) * 300} color={["#A9B8D6", "#94A6CA", "#B9C6E0"][i % 3]} seed={i} />
      ))}
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      {Array.from({ length: 10 }, (_, i) => (
        <Building key={i} x={X0 + i * (WW / 10) + 40} y={0.88 * H} w={WW / 10 - 80} h={200 + rnd(i + 11) * 220} color={[R.paperMid, "#F2B8A0", R.scarfLight][i % 3]} seed={i + 30} />
      ))}
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#B9B4C4" shade="#9893A8" />
      <rect x={X0} y={GY + 70} width={WW} height={12} fill="#FFFFFF" opacity={0.6} />
      <Tree x={0.04 * W} y={GY + 10} s={0.8} f={f} />
      <Tree x={0.95 * W} y={GY + 10} s={0.8} f={f} seed={3} />
      <rect x={0.84 * W} y={GY - 160} width={12} height={160} fill={INK} />
      <circle cx={0.84 * W + 6} cy={GY - 170} r={22} fill={R.glow} {...ol()} />
    </Layer>
  );
};

const lab: ThemeFn = (layer, f) => {
  const beaker = (x: number, y: number, c: string, i: number) => (
    <g key={i} transform={`translate(${x} ${y})`}>
      <path d="M-24 -100 L-24 -60 L-50 0 L50 0 L24 -60 L24 -100Z" fill="#E8F4FA" {...ol()} />
      <path d={`M-40 -20 L40 -20 L50 0 L-50 0Z`} fill={c} />
      {[0, 1, 2].map((k) => {
        const t = ((f * 0.8 + k * 30 + i * 20) % 90) / 90;
        return <circle key={k} cx={(k - 1) * 12} cy={-20 - t * 90} r={5 * (1 - t) + 2} fill={c} opacity={1 - t} />;
      })}
    </g>
  );
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-lab" stops={[[0, "#E8F2F0"], [1, "#CFE2DE"]]} />
      <rect x={0.18 * W} y={0.12 * H} width={0.64 * W} height={0.4 * H} rx={10} fill="#2E5A4E" {...ol()} />
      <rect x={0.18 * W} y={0.12 * H} width={0.64 * W} height={0.4 * H} rx={10} fill="none" stroke={R.pack} strokeWidth={18} />
      <path d={`M${0.25 * W} ${0.4 * H} Q${0.32 * W} ${0.2 * H} ${0.4 * W} ${0.4 * H} T${0.55 * W} ${0.4 * H}`} fill="none" stroke="#FFFFFF" strokeWidth={5} opacity={0.8} />
      <circle cx={0.68 * W} cy={0.3 * H} r={50} fill="none" stroke="#FFFFFF" strokeWidth={5} opacity={0.8} />
      <circle cx={0.68 * W} cy={0.3 * H} r={10} fill="#FFFFFF" opacity={0.8} />
      {Array.from({ length: 3 }, (_, k) => <ellipse key={k} cx={0.68 * W} cy={0.3 * H} rx={90} ry={30} fill="none" stroke="#FFFFFF" strokeWidth={3} opacity={0.6} transform={`rotate(${k * 60} ${0.68 * W} ${0.3 * H})`} />)}
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      <rect x={-0.3 * W} y={0.7 * H} width={0.52 * W} height={40} rx={8} fill="#9AA5B1" {...ol()} />
      {beaker(0.05 * W, 0.7 * H, R.scarfLight, 1)}
      {beaker(0.15 * W, 0.7 * H, R.flower, 2)}
      <rect x={0.8 * W} y={0.7 * H} width={0.5 * W} height={40} rx={8} fill="#9AA5B1" {...ol()} />
      {beaker(0.86 * W, 0.7 * H, R.glow, 3)}
      <g transform={`translate(${0.95 * W} ${0.7 * H})`}>
        <rect x={-30} y={-40} width={60} height={40} rx={6} fill={R.navy} {...ol()} />
        <path d="M0 -40 L30 -200" {...ol(14)} />
        <circle cx={30} cy={-200} r={24} fill={R.brass} {...ol()} />
      </g>
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#DDE6E4" shade="#BCCBC8" />
      {Array.from({ length: 24 }, (_, i) => <path key={i} d={`M${X0 + i * 240} ${GY} V${GY + 0.6 * H}`} stroke="#BCCBC8" strokeWidth={4} />)}
      <rect x={1.02 * W} y={GY - 240} width={70} height={240} rx={8} fill={R.shoe} {...ol()} />
    </Layer>
  );
};

const library: ThemeFn = (layer, f) => {
  const shelf = (x: number, y: number, w: number, rows: number, seed: number) => (
    <g>
      <rect x={x} y={y} width={w} height={rows * 130 + 30} fill={R.packDark} {...ol()} />
      {Array.from({ length: rows }, (_, r) => (
        <g key={r}>
          {Array.from({ length: Math.floor(w / 36) - 1 }, (_, b) => {
            const h = 80 + rnd(seed + r * 31 + b) * 30;
            return <rect key={b} x={x + 20 + b * 36} y={y + 20 + r * 130 + (110 - h)} width={30} height={h} rx={3}
              fill={[R.shoe, R.scarf, R.bedroll, R.brass, R.paperMid, R.flower][(b + r + seed) % 6]} {...ol(3)} />;
          })}
          <rect x={x} y={y + 130 + r * 130} width={w} height={16} fill={R.pack} {...ol(3.5)} />
        </g>
      ))}
    </g>
  );
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-library" stops={[[0, "#D9B98A"], [1, "#B58F62"]]} />
      {shelf(-0.9 * W, -0.2 * H, 0.8 * W, 7, 1)}
      {shelf(0.05 * W, -0.2 * H, 0.9 * W, 7, 2)}
      {shelf(1.1 * W, -0.2 * H, 0.8 * W, 7, 3)}
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      <Motes f={f} n={20} seed={44} color="#FFF4D0" r={2.5} />
      <g transform={`translate(${0.1 * W} ${0.72 * H})`}>
        <rect x={-120} y={0} width={240} height={30} rx={6} fill={R.pack} {...ol()} />
        <circle cx={0} cy={-60} r={56} fill={R.water} {...ol()} />
        <path d="M0 0 L0 -4" {...ol(10)} />
      </g>
    </Layer>
  );
  return (
    <Layer>
      <Ground y={GY} color="#A0603A" shade="#7C4628" />
      <rect x={-0.1 * W} y={GY + 30} width={0.6 * W} height={0.3 * H} rx={20} fill="#C4513E" opacity={0.85} />
      <rect x={0.88 * W} y={GY - 120} width={180} height={120} rx={10} fill={R.paper} {...ol()} />
    </Layer>
  );
};

const night: ThemeFn = (layer, f) => {
  if (layer === "far") return (
    <Layer>
      <Backdrop id="bg-night" stops={[[0, "#0F1838"], [1, "#34477F"]]} />
      <Stars f={f} n={180} seed={21} yMax={0.75 * H} />
      <g transform={`translate(${0.8 * W} ${0.16 * H})`}>
        <circle r={70} fill="#FFF3C8" opacity={0.2} transform="scale(1.6)" />
        <circle r={70} fill="#FFF3C8" {...ol()} />
        <circle cx={-20} cy={-14} r={12} fill="#E8D9A8" />
        <circle cx={22} cy={18} r={8} fill="#E8D9A8" />
      </g>
      <Hills y={0.82 * H} amp={150} color="#2C3E66" shade="#1E2C4E" seed={5} />
    </Layer>
  );
  if (layer === "mid") return (
    <Layer>
      {Array.from({ length: 10 }, (_, i) => <Pine key={i} x={X0 + i * (WW / 10) + rnd(i) * 120} y={0.87 * H} s={0.7} f={f} color="#22365A" shade="#16264A" seed={i} />)}
      <Motes f={f} n={24} seed={6} color="#D8FF7A" r={3} yMin={0.5 * H} yMax={0.95 * H} />
    </Layer>
  );
  const fire = Math.sin(f / 3) * 4;
  return (
    <Layer>
      <Ground y={GY} color="#2E4A3E" shade="#1F3A2E" amp={8} seed={30} />
      <g transform={`translate(${0.86 * W} ${GY + 30})`}>
        <path d="M-150 0 L0 -200 L150 0Z" fill={R.shoe} {...ol()} />
        <path d="M0 -200 L40 0 L-40 0Z" fill={R.shoeDark} {...ol()} />
      </g>
      <g transform={`translate(${0.12 * W} ${GY + 40})`}>
        <circle r={160} fill={R.glow} opacity={0.18} />
        <path d="M-50 0 L50 -14 M-50 -14 L50 0" {...ol(14)} />
        <path d={`M-30 -10 C-40 -60 ${-10 + fire} -80 0 -120 C10 -80 40 -60 30 -10Z`} fill="#FF8A3D" {...ol(4)} />
        <path d={`M-14 -10 C-18 -40 ${-4 - fire} -50 0 -74 C6 -50 18 -40 14 -10Z`} fill={R.glow} />
      </g>
    </Layer>
  );
};

/* ------------------------------------------------------------- studio (neutral fallback) */

const studio: ThemeFn = (layer) => {
  if (layer === "far") return (
    <Layer>
      <rect x={X0} y={Y0} width={WW} height={HH} fill={R.bg} />
      <g transform={`translate(${X0} ${Y0})`}><Topo w={WW} h={HH} color={R.topo} strokeWidth={3} /></g>
    </Layer>
  );
  if (layer === "near") return <Layer><Ground y={GY} color="#E9DFCC" shade="#D6C8AE" outline={false} /></Layer>;
  return <Layer />;
};

export const THEMES = {
  attic: attic(false), workbench: attic(true), sunbeam, sky, air, sunset, mars, space, studio,
  forest, jungle, ocean, underwater, desert, mountains, arctic, volcano, cave, city, lab, library, night,
} satisfies Record<string, ThemeFn>;

export type ThemeId = keyof typeof THEMES;
export const THEME_IDS = Object.keys(THEMES) as ThemeId[];
