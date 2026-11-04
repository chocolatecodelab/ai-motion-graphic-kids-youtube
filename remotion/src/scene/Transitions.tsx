// Scene transitions. transition_in reveals the scene, transition_out covers it, so two
// consecutive scene clips join seamlessly when concatenated.
import React from "react";
import { AbsoluteFill, Easing, interpolate } from "remotion";
import { C } from "../brand";
import type { PlanTransition } from "../types";
import { H, W } from "./layout";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// cover: 0 = scene fully visible, 1 = fully covered.
const Cover: React.FC<{ type: PlanTransition["type"]; cover: number; t: number }> = ({ type, cover, t }) => {
  if (cover <= 0.001 || type === "cut") return null;
  switch (type) {
    case "compass_portal": {
      const r = interpolate(cover, [0, 1], [0, Math.hypot(W, H) * 0.6]);
      return (
        <AbsoluteFill>
          <svg width={W} height={H}>
            <defs>
              <radialGradient id="portal">
                <stop offset="0" stopColor="#E9FFF8" /><stop offset="0.55" stopColor={C.teal} /><stop offset="1" stopColor="#2C7D6E" />
              </radialGradient>
            </defs>
            <circle cx={W / 2} cy={H / 2} r={r} fill="url(#portal)" />
            <circle cx={W / 2} cy={H / 2} r={r} fill="none" stroke={C.brass} strokeWidth={28} />
            {Array.from({ length: 8 }, (_, i) => {
              const a = (i / 8) * Math.PI * 2 + t / 6;
              return <circle key={i} cx={W / 2 + Math.cos(a) * r * 0.7} cy={H / 2 + Math.sin(a) * r * 0.7} r={14} fill={C.yellow} opacity={0.8} />;
            })}
          </svg>
        </AbsoluteFill>
      );
    }
    case "wipe":
      return <AbsoluteFill style={{ background: C.teal, clipPath: `polygon(0 0, ${cover * 130}% 0, ${cover * 130 - 30}% 100%, 0 100%)` }} />;
    case "fade":
      return <AbsoluteFill style={{ background: C.cream, opacity: cover }} />;
    case "zoom_through":
      return <AbsoluteFill style={{ background: C.white, opacity: interpolate(cover, [0.5, 1], [0, 1], clamp) }} />;
    case "whip":
      return (
        <AbsoluteFill style={{ opacity: interpolate(cover, [0, 0.4, 1], [0, 0.9, 1], clamp),
          background: `repeating-linear-gradient(0deg, ${C.cream} 0 14px, rgba(244,240,232,0.6) 14px 28px)`,
          translate: `${interpolate(cover, [0, 1], [W, 0], clamp)}px 0px` }} />
      );
    default:
      return null;
  }
};

export const SceneTransitions: React.FC<{ frame: number; duration: number; tin: PlanTransition; tout: PlanTransition }> = ({
  frame, duration, tin, tout,
}) => {
  const coverIn = tin.frames > 0 ? interpolate(frame, [0, tin.frames], [1, 0], { ...clamp, easing: Easing.inOut(Easing.cubic) }) : 0;
  const coverOut = tout.frames > 0
    ? interpolate(frame, [duration - tout.frames, duration - 1], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) })
    : 0;
  return (
    <>
      <Cover type={tin.type} cover={coverIn} t={frame} />
      <Cover type={tout.type} cover={coverOut} t={frame} />
    </>
  );
};

// Zoom-through / whip also move the image itself, not only the overlay.
export const transitionCameraBoost = (frame: number, duration: number, tin: PlanTransition, tout: PlanTransition) => {
  let zoom = 1;
  let dx = 0;
  if (tout.type === "zoom_through" && tout.frames > 0)
    zoom *= interpolate(frame, [duration - tout.frames, duration], [1, 2.4], { ...clamp, easing: Easing.in(Easing.cubic) });
  if (tin.type === "zoom_through" && tin.frames > 0)
    zoom *= interpolate(frame, [0, tin.frames], [0.6, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  if (tout.type === "whip" && tout.frames > 0)
    dx -= interpolate(frame, [duration - tout.frames, duration], [0, 0.6 * W], { ...clamp, easing: Easing.in(Easing.cubic) });
  if (tin.type === "whip" && tin.frames > 0)
    dx += interpolate(frame, [0, tin.frames], [0.6 * W, 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  return { zoom, dx };
};
