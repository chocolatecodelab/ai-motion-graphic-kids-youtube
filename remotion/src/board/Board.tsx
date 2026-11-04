import React from "react";
import { FONT_BODY } from "../brand";
import { C, SWATCHES } from "../rig/palette";
import { Arka } from "../rig/Arka";
import { Lipa, LIPA_EXPRESSIONS, LIPA_EXPRESSION_NAMES, LIPA_POSES, LIPA_POSE_NAMES } from "../rig/lipa";
import { ARKA_EXPRESSIONS, ARKA_EXPRESSION_NAMES, ARKA_POSES, ArkaPoseName, walkPose } from "../rig/arkaData";
import { POSE_FACE } from "../rig/presets";
import { Topo } from "../rig/Topo";
import { sparklePath } from "../rig/math";

export const BOARD_W = 2400;
export const BOARD_H = 2060;

// Bundled OFL font (public/fonts) so the sheet renders offline and deterministically.
const HEAD = `${FONT_BODY}, sans-serif`;
const BODY = `${FONT_BODY}, sans-serif`;
const MUTED = "#6E6784";

const BOARD_POSES: ArkaPoseName[] = [
  "idle",
  "talk",
  "point",
  "think",
  "surprised",
  "celebrate",
  "walk",
  "hold_map",
  "hold_compass",
  "look_out",
  "crouch",
  "wave",
];

const Card: React.FC<{ x: number; y: number; w: number; h: number; title: string; tag?: string; children?: React.ReactNode }> = ({
  x,
  y,
  w,
  h,
  title,
  tag,
  children,
}) => (
  <g transform={`translate(${x} ${y})`}>
    <rect x={0} y={8} width={w} height={h} rx={30} fill={C.ink} opacity={0.06} />
    <rect x={0} y={0} width={w} height={h} rx={30} fill={C.card} stroke="#E9E0CF" strokeWidth={2} />
    <text x={34} y={62} fontFamily={HEAD} fontWeight={600} fontSize={42} fill={C.navy}>
      {title}
    </text>
    {tag && (
      <g transform={`translate(${w - 34} 30)`}>
        <rect x={-tag.length * 11.5 - 28} y={0} width={tag.length * 11.5 + 28} height={40} rx={20} fill="#EFE7D6" />
        <text x={-14} y={27} textAnchor="end" fontFamily={BODY} fontWeight={800} fontSize={19} fill={MUTED} letterSpacing={0.6}>
          {tag}
        </text>
      </g>
    )}
    {children}
  </g>
);

const Label: React.FC<{ x: number; y: number; children: React.ReactNode; size?: number; color?: string }> = ({ x, y, children, size = 25, color = C.ink }) => (
  <text x={x} y={y} textAnchor="middle" fontFamily={BODY} fontWeight={800} fontSize={size} fill={color}>
    {children}
  </text>
);

const Corners: React.FC<{ w: number; h: number; color: string }> = ({ w, h, color }) => {
  const L = 12;
  const i = 10;
  return (
    <g stroke={color} strokeWidth={2.4} strokeLinecap="round" fill="none" opacity={0.7}>
      <path d={`M${i} ${i + L} V${i} H${i + L}`} />
      <path d={`M${w - i - L} ${i} H${w - i} V${i + L}`} />
      <path d={`M${i} ${h - i - L} V${h - i} H${i + L}`} />
      <path d={`M${w - i - L} ${h - i} H${w - i} V${h - i - L}`} />
    </g>
  );
};

export const Board: React.FC<{ fontCss?: string }> = ({ fontCss = "" }) => {
  const T = 0.35;
  /* --- card geometry --- */
  const M = 48;
  const innerW = BOARD_W - M * 2;
  const poseY = 196;
  const poseH = 560;
  const row2Y = poseY + poseH + 26;
  const row2H = 620;
  const exprW = 1400;
  const lipaW = innerW - exprW - 24;
  const row3Y = row2Y + row2H + 26;
  const row3H = 560;
  const walkW = 1100;
  const palW = 600;
  const scaleW = innerW - walkW - palW - 48;

  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={BOARD_W} height={BOARD_H} viewBox={`0 0 ${BOARD_W} ${BOARD_H}`}>
      <defs>
        <style>{fontCss}</style>
        <clipPath id="board-clip">
          <rect width={BOARD_W} height={BOARD_H} />
        </clipPath>
        <linearGradient id="lipa-tile" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2C3A70" />
          <stop offset="1" stopColor={C.navyDeep} />
        </linearGradient>
        <linearGradient id="expr-tile" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#EAF4EF" />
          <stop offset="1" stopColor="#DCEDE5" />
        </linearGradient>
      </defs>

      {/* paper + contour backdrop */}
      <rect width={BOARD_W} height={BOARD_H} fill={C.bg} />
      <g clipPath="url(#board-clip)">
        <Topo w={BOARD_W} h={BOARD_H} color={C.topo} strokeWidth={2.2} />
      </g>

      {/* header */}
      <text x={M + 4} y={150} fontFamily={HEAD} fontWeight={700} fontSize={112} fill={C.navy} letterSpacing={-1}>
        Arka &amp; Lipa
      </text>
      <path d={sparklePath(20)} transform="translate(668 66)" fill={C.glow} stroke={C.ink} strokeWidth={3} strokeLinejoin="round" />
      <text x={730} y={118} fontFamily={BODY} fontWeight={800} fontSize={27} fill={MUTED}>
        Character Bible v2 · reference sheet rendered from the production rig (rig.v2)
      </text>
      <text x={730} y={154} fontFamily={BODY} fontWeight={700} fontSize={24} fill={MUTED} opacity={0.85}>
        Expedition series · React/SVG · IK limbs with soft joints · smooth motion · draft for owner review
      </text>
      {/* stamp */}
      <g transform={`translate(${BOARD_W - 190} 104) rotate(-7)`}>
        <rect x={-150} y={-58} width={300} height={116} rx={18} fill="none" stroke={C.shoe} strokeWidth={5} />
        <rect x={-140} y={-48} width={280} height={96} rx={12} fill="none" stroke={C.shoe} strokeWidth={2} strokeDasharray="7 7" />
        <text x={0} y={-6} textAnchor="middle" fontFamily={HEAD} fontWeight={700} fontSize={38} fill={C.shoe} letterSpacing={3}>
          EXPEDITION
        </text>
        <text x={0} y={32} textAnchor="middle" fontFamily={BODY} fontWeight={800} fontSize={22} fill={C.shoe} letterSpacing={4}>
          No.01 · RIG.V2
        </text>
      </g>

      {/* ---------------- poses ---------------- */}
      <Card x={M} y={poseY} w={innerW} h={poseH} title="Arka: poses" tag="12 POSES · INTERPOLATABLE">
        {BOARD_POSES.map((n, i) => {
          const cw = innerW / 12;
          const cx = cw * i + cw / 2;
          return (
            <g key={n}>
              <g transform={`translate(${cx} ${474}) scale(0.8)`}>
                <Arka uid={`pose-${n}`} pose={ARKA_POSES[n]} expression={POSE_FACE[n]} t={T + i * 0.37} />
              </g>
              <Label x={cx} y={526}>
                {n}
              </Label>
            </g>
          );
        })}
      </Card>

      {/* ---------------- expressions ---------------- */}
      <Card x={M} y={row2Y} w={exprW} h={row2H} title="Arka: expressions" tag="10 FACES">
        {ARKA_EXPRESSION_NAMES.map((n, i) => {
          const tw = 254;
          const th = 206;
          const gap = 15;
          const col = i % 5;
          const row = Math.floor(i / 5);
          const x = 34 + col * (tw + gap);
          const y = 96 + row * (th + 50);
          return (
            <g key={n} transform={`translate(${x} ${y})`}>
              <rect width={tw} height={th} rx={20} fill="url(#expr-tile)" />
              <svg x={0} y={0} width={tw} height={th} viewBox="-127 -386 254 206">
                <Arka uid={`expr-${n}`} pose={ARKA_POSES.idle} expression={ARKA_EXPRESSIONS[n]} t={T + i * 0.21} shadow={false} breathe={false} />
              </svg>
              <Corners w={tw} h={th} color={C.scarf} />
              <Label x={tw / 2} y={th + 34}>
                {n}
              </Label>
            </g>
          );
        })}
      </Card>

      {/* ---------------- Lipa ---------------- */}
      <Card x={M + exprW + 24} y={row2Y} w={lipaW} h={row2H} title="Lipa: expressions + poses" tag="MAP-BIRD">
        {LIPA_EXPRESSION_NAMES.map((n, i) => {
          const tw = 196;
          const th = 132;
          const col = i % 4;
          const row = Math.floor(i / 4);
          const x = 30 + col * (tw + 12);
          const y = 96 + row * (th + 46);
          return (
            <g key={n} transform={`translate(${x} ${y})`}>
              <rect width={tw} height={th} rx={18} fill="url(#lipa-tile)" />
              <svg x={0} y={0} width={tw} height={th} viewBox="-92 -100 196 132">
                <Lipa uid={`lexp-${n}`} pose={LIPA_POSES.float} expression={LIPA_EXPRESSIONS[n]} t={0.2 + i * 0.13} trail={false} />
              </svg>
              <Label x={tw / 2} y={th + 30} size={22}>
                {n}
              </Label>
            </g>
          );
        })}
        {LIPA_POSE_NAMES.map((n, i) => {
          const tw = 129;
          const th = 104;
          const x = 30 + i * (tw + 10);
          const y = 460;
          return (
            <g key={n} transform={`translate(${x} ${y})`}>
              <rect width={tw} height={th} rx={16} fill="url(#lipa-tile)" />
              <svg x={0} y={0} width={tw} height={th} viewBox="-100 -110 220 177">
                <Lipa uid={`lpose-${n}`} pose={LIPA_POSES[n]} expression={LIPA_EXPRESSIONS.neutral} t={0.25 + i * 0.2} />
              </svg>
              <Label x={tw / 2} y={th + 28} size={20}>
                {n}
              </Label>
            </g>
          );
        })}
      </Card>

      {/* ---------------- walk cycle ---------------- */}
      <Card x={M} y={row3Y} w={walkW} h={row3H} title="Walk cycle" tag="8 KEYS · 24F LOOP @ 30FPS">
        <path d={`M40 ${436} H${walkW - 40}`} stroke={C.topo} strokeWidth={4} strokeLinecap="round" />
        {Array.from({ length: 8 }).map((_, i) => {
          const fx = 96 + i * 130;
          return (
            <g key={i}>
              <g transform={`translate(${fx} 434) scale(0.57)`}>
                <Arka uid={`walk-${i}`} pose={walkPose(i / 8)} expression={POSE_FACE.walk} t={i * 0.1} breathe={false} />
              </g>
              <circle cx={fx} cy={478} r={17} fill={i === 0 || i === 4 ? C.shoe : "#EFE7D6"} />
              <text x={fx} y={485} textAnchor="middle" fontFamily={BODY} fontWeight={800} fontSize={18} fill={i === 0 || i === 4 ? "#fff" : MUTED}>
                {String(i * 3 + 1).padStart(2, "0")}
              </text>
            </g>
          );
        })}
        <text x={40} y={530} fontFamily={BODY} fontWeight={700} fontSize={20} fill={MUTED}>
          walkPose(phase): eased foot lift, hip bob + sway, contact squash, counter-swing arms · coral = contact frames
        </text>
      </Card>

      {/* ---------------- palette ---------------- */}
      <Card x={M + walkW + 24} y={row3Y} w={palW} h={row3H} title="Palette" tag="14 TOKENS">
        {SWATCHES.map((s, i) => {
          const col = i % 4;
          const row = Math.floor(i / 4);
          const sw = 124;
          const x = 34 + col * (sw + 10);
          const y = 96 + row * 112;
          return (
            <g key={s.name} transform={`translate(${x} ${y})`}>
              <rect width={sw} height={56} rx={14} fill={s.hex} stroke={C.ink} strokeWidth={2.4} />
              <text x={sw / 2} y={78} textAnchor="middle" fontFamily={BODY} fontWeight={800} fontSize={16} fill={C.ink}>
                {s.name}
              </text>
              <text x={sw / 2} y={98} textAnchor="middle" fontFamily={BODY} fontWeight={700} fontSize={15} fill={MUTED}>
                {s.hex}
              </text>
            </g>
          );
        })}
      </Card>

      {/* ---------------- scale & facing ---------------- */}
      <Card x={M + walkW + palW + 48} y={row3Y} w={scaleW} h={row3H} title="Scale & facing">
        {[0, 0.25, 0.5, 0.75, 1].map((k) => {
          const y = 466 - k * 350;
          return (
            <g key={k}>
              <path d={`M40 ${y} H${scaleW - 30}`} stroke="#E9E0CF" strokeWidth={2} strokeDasharray={k === 0 ? "0" : "6 8"} />
              <text x={36} y={y - 6} fontFamily={BODY} fontWeight={800} fontSize={15} fill={MUTED}>
                {k === 0 ? "0" : k === 1 ? "H" : `${k}H`}
              </text>
            </g>
          );
        })}
        <g transform="translate(150 466) scale(0.84)">
          <Arka uid="scale-a" pose={ARKA_POSES.point} expression={POSE_FACE.point} t={0.6} />
        </g>
        <g transform="translate(286 214) scale(0.76)">
          <Lipa uid="scale-l" pose={LIPA_POSES.float} expression={LIPA_EXPRESSIONS.delighted} t={0.3} />
        </g>
        <g transform="translate(445 466) scale(0.84)">
          <Arka uid="scale-b" pose={ARKA_POSES.hold_compass} expression={POSE_FACE.hold_compass} t={0.9} facing={-1} />
        </g>
        <text x={scaleW / 2} y={528} textAnchor="middle" fontFamily={BODY} fontWeight={800} fontSize={19} fill={C.ink}>
          Lipa ≈ 1/4 of Arka&apos;s height · facing right / left (mirror)
        </text>
      </Card>

      {/* footer */}
      <text x={M + 4} y={BOARD_H - 30} fontFamily={BODY} fontWeight={700} fontSize={21} fill={MUTED}>
        rig.v2 · Arka 14 poses × 10 expressions · Lipa 6 poses × 8 expressions · all poses are numeric &amp; blendable (lerpPose) · tokens: src/rig/palette.ts
      </text>
      <text x={BOARD_W - M - 4} y={BOARD_H - 30} textAnchor="end" fontFamily={BODY} fontWeight={800} fontSize={21} fill={C.navy}>
        Remotion 4 · 1920×1080 · 30 fps
      </text>
    </svg>
  );
};
