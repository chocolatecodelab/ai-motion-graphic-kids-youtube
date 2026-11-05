// Review sheet for the M2 SVG scene library: every theme with Arka & Lipa for scale/contrast.
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { FONT_BODY } from "./brand";
import { Arka } from "./rig/Arka";
import { ARKA_POSES } from "./rig/arkaData";
import { Lipa, LIPA_EXPRESSIONS, LIPA_POSES } from "./rig/lipa";
import { C as R } from "./rig/palette";
import { POSE_FACE } from "./rig/presets";
import { BackgroundLayer } from "./scene/Backgrounds";
import { THEME_IDS } from "./scene/bg/themes";
import type { Theme } from "./types";

const COLS = 4;
const TW = 480;
const TH = 270;
const GAP = 28;
export const BG_SHEET_W = COLS * TW + (COLS + 1) * GAP;
export const BG_SHEET_H = 140 + Math.ceil(THEME_IDS.length / COLS) * (TH + 64) + GAP;

const Thumb: React.FC<{ theme: Theme; frame: number }> = ({ theme, frame }) => (
  <div style={{ position: "absolute", width: 1920, height: 1080, overflow: "hidden", transform: `scale(${TW / 1920})`, transformOrigin: "0 0" }}>
    {(["far", "mid", "near"] as const).map((l) => (
      <div key={l} style={{ position: "absolute", inset: 0 }}><BackgroundLayer theme={theme} layer={l} frame={frame} /></div>
    ))}
    <svg viewBox="-150 -440 300 460" width={300 * 1.6} height={460 * 1.6}
      style={{ position: "absolute", left: 960 - 150 * 1.6, top: 0.93 * 1080 - 440 * 1.6 + 6, overflow: "visible" }}>
      <Arka uid={`bgs-${theme}`} pose={ARKA_POSES.idle} expression={POSE_FACE.idle} t={0.4} />
    </svg>
    <svg viewBox="-130 -130 260 260" width={260 * 1.3} height={260 * 1.3}
      style={{ position: "absolute", left: 1320 - 130 * 1.3, top: 380 - 130 * 1.3, overflow: "visible" }}>
      <Lipa uid={`bgl-${theme}`} pose={LIPA_POSES.float} expression={LIPA_EXPRESSIONS.delighted} t={0.3} />
    </svg>
  </div>
);

export const BackgroundSheet: React.FC = () => {
  const frame = useCurrentFrame() + 60; // a moment into the loops (clouds, waves, smoke)
  return (
    <AbsoluteFill style={{ backgroundColor: R.bg, fontFamily: `${FONT_BODY}, sans-serif` }}>
      <div style={{ position: "absolute", left: GAP, top: 36, fontSize: 64, fontWeight: 800, color: R.navy }}>Scene library</div>
      <div style={{ position: "absolute", left: GAP + 420, top: 60, fontSize: 26, fontWeight: 700, color: "#6E6784" }}>
        {THEME_IDS.length} environments · 3 parallax layers each · ambient motion · Arka &amp; Lipa for scale
      </div>
      {THEME_IDS.map((t, i) => {
        const x = GAP + (i % COLS) * (TW + GAP);
        const y = 140 + Math.floor(i / COLS) * (TH + 64);
        return (
          <div key={t} style={{ position: "absolute", left: x, top: y }}>
            <div style={{ position: "relative", width: TW, height: TH, borderRadius: 18, overflow: "hidden", boxShadow: "0 6px 0 rgba(43,34,64,0.12)", border: `3px solid ${R.ink}` }}>
              <Thumb theme={t as Theme} frame={frame} />
            </div>
            <div style={{ marginTop: 10, fontSize: 28, fontWeight: 800, color: R.ink, textAlign: "center", width: TW }}>{t}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
