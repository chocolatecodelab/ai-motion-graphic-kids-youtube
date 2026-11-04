// On-screen captions (owner decision D7): big rounded text, current word highlighted,
// speaker colour cue. Sits in the lower safe area, below where faces are framed.
import React from "react";
import { Easing, interpolate } from "remotion";
import { C, FONT_BODY } from "../brand";
import type { PlanCaption } from "../types";

const SPEAKER: Record<string, string> = { arka: C.teal, lipa: C.yellow, kai: C.teal, needle: C.yellow };
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Captions: React.FC<{ captions: PlanCaption[]; frame: number }> = ({ captions, frame }) => {
  const cap = captions.find((c) => frame >= c.start_frame && frame < c.end_frame);
  if (!cap) return null;
  const t = frame - cap.start_frame;
  const appear = interpolate(t, [0, 5], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <div style={{
      position: "absolute", left: "50%", bottom: 54, translate: `-50% ${(1 - appear) * 16}px`,
      opacity: appear, display: "flex", alignItems: "center", gap: 22,
      padding: "18px 38px 20px 30px", borderRadius: 34, maxWidth: 1500,
      background: "rgba(29,43,79,0.86)", boxShadow: "0 10px 30px rgba(0,0,0,0.28)",
      border: `4px solid ${SPEAKER[cap.speaker]}`,
    }}>
      <div style={{ width: 26, height: 26, borderRadius: "50%", background: SPEAKER[cap.speaker], flexShrink: 0 }} />
      <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 62, lineHeight: 1.12, color: C.white,
        textAlign: "center", letterSpacing: 0.5 }}>
        {cap.lines.map((line, i) => (
          <div key={i}>
            {line.map((w, k) => {
              const current = frame >= w.start_frame && frame < w.end_frame;
              const spoken = frame >= w.start_frame;
              return (
                <span key={k} style={{
                  display: "inline-block", marginRight: k < line.length - 1 ? "0.28em" : 0,
                  color: current ? C.yellow : C.white, opacity: spoken ? 1 : 0.8,
                  scale: current ? "1.08" : "1", textShadow: "0 3px 0 rgba(0,0,0,0.35)",
                }}>{w.text}</span>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};
