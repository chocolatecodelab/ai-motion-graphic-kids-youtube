// Set-dressing props placed by the visual_plan agent (config/catalogue/props_v1.yaml).
// Built-ins are drawn from the kit; generated assets arrive as sanitised SVG markup (the
// Python assets stage allowlists elements/attributes, so it is safe to inline).
import React from "react";
import { C as R } from "../../rig/palette";
import type { PlanProp } from "../../types";
import { H, W } from "../layout";
import { Bush, ol, Pine, Rock, Tree } from "./kit";

type Draw = (f: number) => React.ReactElement;
const g = (node: React.ReactNode) => <g>{node}</g>;

// Each draws with its base at (0, 0), growing upwards (negative y), at natural size.
const BUILTIN: Record<string, Draw> = {
  tree: (f) => <Tree x={0} y={0} s={0.95} f={f} />,
  pine: (f) => <Pine x={0} y={0} s={1} f={f} />,
  bush: () => <Bush x={0} y={0} s={0.9} berries />,
  rock: () => <Rock x={0} y={0} s={1} />,
  cactus: () => g(
    <>
      <path d="M-22 0 L-22 -200 C-22 -230 22 -230 22 -200 L22 0Z" fill="#5FA368" {...ol()} />
      <path d="M-22 -110 L-60 -110 C-80 -110 -80 -150 -80 -170 C-80 -190 -56 -190 -56 -170 L-56 -136 L-22 -136" fill="#5FA368" {...ol()} />
      <path d="M22 -80 L56 -80 L56 -130 C56 -150 80 -150 80 -130 L80 -90 C80 -60 60 -56 22 -56" fill="#5FA368" {...ol()} />
      <circle cx={0} cy={-226} r={10} fill={R.flower} {...ol(3)} />
    </>,
  ),
  crystal: (f) => g(
    <>
      <circle cy={-50} r={80} fill="#7FD3E8" opacity={0.18 + 0.1 * Math.sin(f / 25)} />
      <path d="M-24 0 L-14 -80 L0 -110 L14 -80 L24 0Z" fill="#7FD3E8" {...ol()} />
      <path d="M16 0 L34 -56 L46 -46 L42 0Z" fill="#B48CF2" {...ol()} />
      <path d="M-6 -80 L0 -102 L4 -80Z" fill="#FFFFFF" opacity={0.6} />
    </>,
  ),
  beaker: (f) => g(
    <>
      <path d="M-24 -110 L-24 -66 L-54 0 L54 0 L24 -66 L24 -110Z" fill="#E8F4FA" {...ol()} />
      <path d="M-44 -22 L44 -22 L54 0 L-54 0Z" fill={R.scarfLight} />
      {[0, 1, 2].map((k) => {
        const t = ((f * 0.8 + k * 30) % 90) / 90;
        return <circle key={k} cx={(k - 1) * 12} cy={-22 - t * 96} r={5 * (1 - t) + 2} fill={R.scarfLight} opacity={1 - t} />;
      })}
    </>,
  ),
  globe: () => g(
    <>
      <path d="M-40 0 L40 0 L20 -24 L-20 -24Z" fill={R.brass} {...ol()} />
      <path d="M0 -24 L0 -44" {...ol(10)} />
      <path d="M-74 -120 A74 74 0 0 0 46 -60" fill="none" stroke={R.brassDark} strokeWidth={10} />
      <circle cy={-120} r={64} fill={R.water} {...ol()} />
      <path d="M-40 -150 C-10 -130 -30 -110 10 -100 C30 -96 30 -80 40 -84" fill="none" stroke={R.land} strokeWidth={18} strokeLinecap="round" />
    </>,
  ),
  books: () => g(
    <>
      {[[R.shoe, 0, 90], [R.scarf, -6, 80], [R.bedroll, 4, 96], [R.brass, -2, 84]].map(([c, dx, w], i) => (
        <rect key={i} x={-(w as number) / 2 + (dx as number)} y={-(i + 1) * 26} width={w as number} height={26} rx={4} fill={c as string} {...ol(4)} />
      ))}
    </>,
  ),
  telescope: () => g(
    <>
      <path d="M0 -110 L-50 0 M0 -110 L50 0 M0 -110 L0 0" {...ol(9)} />
      <g transform="translate(0 -120) rotate(-28)">
        <rect x={-90} y={-18} width={150} height={36} rx={10} fill={R.brass} {...ol()} />
        <rect x={50} y={-24} width={46} height={48} rx={8} fill={R.brassDark} {...ol()} />
        <rect x={-110} y={-12} width={24} height={24} rx={4} fill={R.navy} {...ol(4)} />
      </g>
    </>,
  ),
  lantern: (f) => g(
    <>
      <circle cy={-60} r={70} fill={R.glow} opacity={0.22 + 0.06 * Math.sin(f / 6)} />
      <rect x={-30} y={-100} width={60} height={90} rx={12} fill="#FFF3C8" {...ol()} />
      <path d={`M0 -30 C-12 -50 ${-2 + Math.sin(f / 4) * 3} -64 0 -80 C6 -64 14 -50 0 -30Z`} fill={R.flower} />
      <rect x={-36} y={-112} width={72} height={16} rx={6} fill={R.ink} />
      <rect x={-36} y={-12} width={72} height={14} rx={6} fill={R.ink} />
      <path d="M-14 -112 Q0 -136 14 -112" fill="none" {...ol(5)} />
    </>,
  ),
  signpost: () => g(
    <>
      <rect x={-8} y={-230} width={16} height={230} fill={R.pack} {...ol()} />
      <path d="M-6 -214 L110 -214 L134 -192 L110 -170 L-6 -170Z" fill={R.paper} {...ol()} />
      <path d="M6 -150 L-110 -150 L-134 -128 L-110 -106 L6 -106Z" fill={R.paperMid} {...ol()} />
      <path d="M30 -192 L96 -192 M-30 -128 L-96 -128" stroke={R.route} strokeWidth={6} strokeDasharray="10 10" strokeLinecap="round" />
    </>,
  ),
};

/** Generated asset: 400x400 viewBox, base centred at (200, 390), drawn ~0.25 H tall at scale 1. */
const SvgProp: React.FC<{ markup: string }> = ({ markup }) => {
  const size = 0.25 * H;
  const inner = markup.replace(/^<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "");
  return (
    <svg x={-size / 2} y={-size * (390 / 400)} width={size} height={size} viewBox="0 0 400 400" overflow="visible"
      dangerouslySetInnerHTML={{ __html: inner }} />
  );
};

/** One placed prop in world coordinates (x, y = ground contact in frame fractions). */
export const PropView: React.FC<{ p: PlanProp; f: number }> = ({ p, f }) => {
  const draw = p.kind === "builtin" ? BUILTIN[p.ref] : undefined;
  if (p.kind === "builtin" && !draw) return null;
  return (
    <g transform={`translate(${(p.x * W).toFixed(1)} ${(p.y * H).toFixed(1)}) scale(${p.flip ? -p.scale : p.scale} ${p.scale})`}>
      {draw ? draw(f) : p.svg ? <SvgProp markup={p.svg} /> : null}
    </g>
  );
};

export const BUILTIN_PROP_IDS = Object.keys(BUILTIN);
