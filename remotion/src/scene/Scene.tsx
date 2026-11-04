// One storyboard scene, rendered from its renderplan.v1 entry.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C } from "../brand";
import { Kai } from "../characters/Kai";
import { Needle } from "../characters/Needle";
import { GraphicView } from "../graphics/Graphics";
import type { PlanGraphic, PlanScene, PlanShot, SceneProps } from "../types";
import { BackgroundLayer, LAYER_PARALLAX, type Layer } from "./Backgrounds";
import { actorAt, ActorState, cameraAt, CameraState, DEPTH_PARALLAX, H, W } from "./layout";
import { SceneTransitions, transitionCameraBoost } from "./Transitions";

const shotAt = (scene: PlanScene, f: number): PlanShot =>
  scene.shots.find((s) => f >= s.start_frame && f < s.end_frame) ?? scene.shots[scene.shots.length - 1];

// World -> screen transform for a parallax factor (1 = moves exactly with the camera).
const worldTransform = (cam: CameraState, k: number, boost: { zoom: number; dx: number }) => {
  const zoom = (1 + (cam.zoom - 1) * k) * boost.zoom;
  const cx = W / 2 + (cam.cx - W / 2) * k;
  const cy = H / 2 + (cam.cy - H / 2) * k;
  return `translate(${W / 2 + boost.dx}px, ${H / 2}px) rotate(${cam.rotate}deg) scale(${zoom}) translate(${-cx}px, ${-cy}px)`;
};

const Actor: React.FC<{ a: ActorState; pose: string; expression: string; action: string | null; mouth: number; talking: boolean; t: number; frame: number }> = ({
  a, pose, expression, action, mouth, talking, t, frame,
}) => {
  const isKai = a.character === "kai";
  const w = isKai ? a.height / 2 : a.height;
  const blink = (frame + (isKai ? 0 : 41)) % 97 < 4;
  const props = { pose, expression, action, mouth, blink, t, walkPhase: a.walkPhase, talking };
  return (
    <div style={{
      position: "absolute", left: a.x - w / 2, top: a.y - a.height, width: w, height: a.height,
      opacity: a.opacity, transformOrigin: "50% 100%",
      transform: `rotate(${a.rotate}deg) scale(${a.scaleX}, ${a.squash})`,
    }}>
      {a.portal > 0 && (
        <div style={{ position: "absolute", left: "50%", bottom: 0, width: w * 1.6, height: w * 0.5,
          translate: "-50% 50%", borderRadius: "50%", border: `10px solid ${C.teal}`, opacity: a.portal, boxShadow: `0 0 30px ${C.teal}` }} />
      )}
      {isKai ? <Kai {...props} /> : <Needle {...props} />}
    </div>
  );
};

const GraphicLayer: React.FC<{ g: PlanGraphic; frame: number; focus: boolean; fps: number; index: number; side: "left" | "right" }> = ({
  g, frame, focus, fps, index, side,
}) => {
  if (frame < g.start_frame || frame >= g.end_frame) return null;
  const t = frame - g.start_frame;
  const len = g.end_frame - g.start_frame;
  const fade = Math.min(1, t / 8, (len - t) / 8);
  // Panels sit on the side away from the characters, so they never cover a face.
  const placement: React.CSSProperties = focus
    ? { left: "50%", top: "50%", translate: "-50% -50%", scale: "1.2" }
    : g.component === "Label"
      ? side === "left" ? { left: 80, top: 70 + index * 110 } : { right: 80, top: 70 + index * 110 }
      : g.component === "Recap"
        ? { left: "50%", top: "50%", translate: "-50% -50%" }
        : side === "left"
          ? { left: 60, top: "50%", translate: "0 -50%", scale: "0.78", transformOrigin: "0 50%" }
          : { right: 60, top: "50%", translate: "0 -50%", scale: "0.78", transformOrigin: "100% 50%" };
  return (
    <div style={{ position: "absolute", opacity: Math.max(0, fade), ...placement }}>
      <GraphicView g={g} t={t} len={len} fps={fps} />
    </div>
  );
};

export const Scene: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shot = shotAt(scene, frame);
  const t = frame - shot.start_frame;
  const len = shot.end_frame - shot.start_frame;

  const actors = shot.blocking.map((b, i) => actorAt(b, t, len, i * 17 + scene.scene_id.length));
  // Camera framing reference: where characters stand (start and end of their paths),
  // ignoring entrances/exits and motion wobble, so a static camera frames the action.
  const rest = (b: PlanShot["blocking"][number]) => ({ ...b, enter: "none" as const, exit: "none" as const, motion: "none" as const });
  const actorsStart = shot.blocking.flatMap((b) => [actorAt(rest(b), 0, len, 0), actorAt(rest(b), len - 1, len, 0)]);
  const cam = cameraAt(shot, t, actors, actorsStart);
  const boost = transitionCameraBoost(frame, scene.duration_frames, scene.transition_in, scene.transition_out);

  // Where the characters stand on screen in this shot -> graphics go on the opposite side.
  // Decided once per shot (rest positions, opening camera) so panels never jump mid-shot.
  const camStart = cameraAt(shot, 0, actorsStart, actorsStart);
  const screenX = actorsStart.map((a) => (a.x - camStart.cx) * camStart.zoom + W / 2);
  const avgX = screenX.length ? screenX.reduce((s, x) => s + x, 0) / screenX.length : W / 2;
  const graphicSide: "left" | "right" = avgX > W / 2 ? "left" : "right";

  const speaking = scene.lines.find((l) => frame >= l.start_frame && frame < l.end_frame);
  const mouthFor = (who: string) =>
    speaking && speaking.speaker === who ? speaking.mouth[frame - speaking.start_frame] ?? 0 : 0;

  const layer = (name: Layer) => (
    <AbsoluteFill style={{ transform: worldTransform(cam, LAYER_PARALLAX[name], boost), transformOrigin: "0 0" }}>
      <BackgroundLayer theme={scene.theme} layer={name} frame={frame} />
    </AbsoluteFill>
  );

  const byDepth = (depth: "background" | "midground" | "foreground") => (
    <AbsoluteFill style={{ transform: worldTransform(cam, DEPTH_PARALLAX[depth], boost), transformOrigin: "0 0" }}>
      {shot.blocking.map((b, i) => b.depth === depth && (
        <Actor key={b.character} a={actors[i]} pose={b.pose} expression={b.expression} action={b.action}
          mouth={mouthFor(b.character)} talking={speaking?.speaker === b.character} t={t} frame={frame} />
      ))}
    </AbsoluteFill>
  );

  return (
    <AbsoluteFill style={{ backgroundColor: C.blue, overflow: "hidden" }}>
      {layer("far")}
      {layer("mid")}
      {layer("near")}
      {byDepth("background")}
      {byDepth("midground")}
      {byDepth("foreground")}
      {scene.graphics.map((g, i) => (
        <GraphicLayer key={i} g={g} frame={frame} fps={fps} index={i} side={graphicSide}
          focus={shot.focus === "graphic" || shot.shot_type === "insert"} />
      ))}
      <SceneTransitions frame={frame} duration={scene.duration_frames} tin={scene.transition_in} tout={scene.transition_out} />
    </AbsoluteFill>
  );
};
