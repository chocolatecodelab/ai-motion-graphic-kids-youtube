// Motion check for the Arka & Lipa rig (Character Bible v2): every pose blending into the
// next with follow-through, the walk cycle, Lipa's flight, and lip-sync. Used to review
// smoothness frame by frame; not part of episodes.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT_BODY } from "./brand";
import { Arka } from "./rig/Arka";
import { ARKA_EXPRESSIONS, ARKA_POSE_NAMES, ARKA_POSES, type ArkaPose, lerpPose, walkPose } from "./rig/arkaData";
import { flightAt, Lipa, LIPA_EXPRESSIONS, LIPA_POSES } from "./rig/lipa";
import { C as RC } from "./rig/palette";
import { POSE_FACE } from "./rig/presets";
import { Topo } from "./rig/Topo";
import { blinkAt, POSE_EASE } from "./scene/puppets";

const HOLD = 18;
const BLEND = 14;
const SEG = HOLD + BLEND;
export const RIG_CHECK_FRAMES = ARKA_POSE_NAMES.length * SEG;

const morphAt = (f: number): { pose: ArkaPose; name: (typeof ARKA_POSE_NAMES)[number] } => {
  const i = Math.floor(Math.max(0, f) / SEG) % ARKA_POSE_NAMES.length;
  const j = (i + 1) % ARKA_POSE_NAMES.length;
  const local = Math.max(0, f) % SEG;
  const k = local < HOLD ? 0 : POSE_EASE((local - HOLD) / BLEND);
  const a = ARKA_POSE_NAMES[i];
  const b = ARKA_POSE_NAMES[j];
  return { pose: lerpPose(ARKA_POSES[a], ARKA_POSES[b], k), name: k < 0.5 ? a : b };
};

const label: React.CSSProperties = { position: "absolute", fontFamily: `${FONT_BODY}, sans-serif`, fontWeight: 800, color: RC.navy };

export const RigCheck: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const { pose, name } = morphAt(frame);
  const back2 = morphAt(frame - 2).pose;
  const back3 = morphAt(frame - 3).pose;
  const overlap = { y: (pose.rootY - back2.rootY) * 0.6, tilt: (back3.lean - pose.lean) * 0.7 };
  const fl = flightAt(t, 2.4);
  // Lip-sync stand-in: a syllable-like amplitude curve.
  const amp = Math.max(0, Math.sin(t * 9.1) * 0.6 + Math.sin(t * 4.3) * 0.4);
  return (
    <AbsoluteFill style={{ backgroundColor: RC.bg }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0 }}>
        <Topo w={width} h={height} color={RC.topo} strokeWidth={2.4} phase={frame * 0.012} opacity={0.5} />
        <path d={`M60 ${height - 118} H${width - 60}`} stroke={RC.topo} strokeWidth={4} strokeLinecap="round" />
        <g transform={`translate(${width * 0.3} ${height - 120}) scale(1.75)`}>
          <Arka uid="rc-morph" pose={pose} expression={POSE_FACE[name]} t={t} blink={blinkAt(frame, 3)} overlap={overlap} />
        </g>
        <g transform={`translate(${width * 0.66} ${height - 120}) scale(0.95)`}>
          <Arka uid="rc-walk" pose={walkPose((frame % 24) / 24)} expression={POSE_FACE.walk} t={t} blink={blinkAt(frame, 11)} />
        </g>
        <g transform={`translate(${width * 0.86} ${height - 120}) scale(0.95)`}>
          <Arka uid="rc-talk" pose={ARKA_POSES.talk} t={t} blink={blinkAt(frame, 19)}
            expression={{ ...ARKA_EXPRESSIONS.delighted, mouth: amp > 0.06 ? "talk" : "smile", mouthOpen: amp }} facing={-1} />
        </g>
        <g transform={`translate(${width * 0.77} ${height * 0.25}) scale(1.5)`}>
          <Lipa uid="rc-lipa" pose={{ ...LIPA_POSES.float, flap: fl.flap }} flapTip={fl.flapTip} bob={fl.bob}
            expression={LIPA_EXPRESSIONS.delighted} t={t} />
        </g>
      </svg>
      <div style={{ ...label, left: 70, top: 50, fontSize: 76 }}>{name}</div>
      <div style={{ ...label, left: 74, top: 140, fontSize: 26, letterSpacing: 4, color: RC.shoe }}>
        RIG.V2 MOTION CHECK · POSE {String(ARKA_POSE_NAMES.indexOf(name) + 1).padStart(2, "0")}/{ARKA_POSE_NAMES.length}
      </div>
      <div style={{ ...label, left: width * 0.6, top: height - 90, fontSize: 24 }}>walk cycle</div>
      <div style={{ ...label, left: width * 0.81, top: height - 90, fontSize: 24 }}>lip-sync</div>
      <div style={{ ...label, left: width * 0.72, top: height * 0.25 + 120, fontSize: 24 }}>Lipa flight</div>
    </AbsoluteFill>
  );
};
