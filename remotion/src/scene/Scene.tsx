// One storyboard scene, rendered from its renderplan.v1 entry.
import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C } from "../brand";
import { GraphicView } from "../graphics/Graphics";
import { Arka } from "../rig/Arka";
import { Lipa } from "../rig/lipa";
import type { PlanGraphic, PlanProp, PlanScene, PlanShot, SceneProps } from "../types";
import { Layer as PropLayer } from "./bg/kit";
import { PropView } from "./bg/props";
import { BackgroundLayer, LAYER_PARALLAX, type Layer } from "./Backgrounds";
import { Captions } from "./Captions";
import { actorAt, ActorState, cameraAt, CameraState, DEPTH_PARALLAX, H, W } from "./layout";
import { arkaFaceAt, arkaOverlap, arkaPoseAt, type ArkaCtx, blinkAt, lipaStateAt } from "./puppets";
import { type Box, placeGraphic, type Placement } from "./placement";
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

// Rig spaces (Character Bible v2): Arka's feet sit at (0,0) and his hat top near y = -410;
// Lipa is drawn around her body centre and is about 140 units across.
const ARKA_UNITS = 410;
const ARKA_VB = { x: -150, y: -440, w: 300, h: 460 };
const LIPA_UNITS = 140;
const LIPA_VB = 130; // half-size of Lipa's square viewBox

const Portal: React.FC<{ strength: number; width: number }> = ({ strength, width }) =>
  strength > 0 ? (
    <div style={{ position: "absolute", left: "50%", bottom: 0, width: width * 1.6, height: width * 0.5,
      translate: "-50% 50%", borderRadius: "50%", border: `10px solid ${C.teal}`, opacity: strength, boxShadow: `0 0 30px ${C.teal}` }} />
  ) : null;

const Actor: React.FC<{ a: ActorState; ctx: ArkaCtx; t: number; frame: number; mouth: number }> = ({ a, ctx, t, frame, mouth }) => {
  const secs = frame / ctx.fps;
  const facing = a.scaleX < 0 ? -1 : 1;
  const uid = `${a.character}-${ctx.seed}`;
  if (a.character === "arka") {
    const ppu = a.height / ARKA_UNITS;
    const w = ARKA_VB.w * ppu;
    const h = ARKA_VB.h * ppu;
    const body = arkaPoseAt(ctx, t);
    // Facing camera = a near-frontal head; otherwise the default 3/4 view.
    const pose = ctx.b.facing === "camera" ? { ...body, turn: Math.max(-1, Math.min(1, body.turn - 0.75)) } : body;
    return (
      <div style={{
        position: "absolute", left: a.x + ARKA_VB.x * ppu, top: a.y + ARKA_VB.y * ppu, width: w, height: h,
        opacity: a.opacity, transformOrigin: `50% ${((-ARKA_VB.y / ARKA_VB.h) * 100).toFixed(2)}%`,
        transform: `rotate(${a.rotate}deg) scaleY(${a.squash})`,
      }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: w, height: -ARKA_VB.y * ppu }}>
          <Portal strength={a.portal} width={w * 0.6} />
        </div>
        <svg viewBox={`${ARKA_VB.x} ${ARKA_VB.y} ${ARKA_VB.w} ${ARKA_VB.h}`} width={w} height={h} style={{ overflow: "visible" }}>
          <Arka pose={pose} expression={arkaFaceAt(ctx, t, mouth)} t={secs + ctx.seed * 0.11} blink={blinkAt(frame, ctx.seed)}
            facing={facing} uid={uid} overlap={arkaOverlap(ctx, t)} />
        </svg>
      </div>
    );
  }
  const ppu = a.height / LIPA_UNITS;
  const size = LIPA_VB * 2 * ppu;
  const lipa = lipaStateAt(ctx, t, mouth);
  return (
    <div style={{
      position: "absolute", left: a.x - size / 2, top: a.y - a.height / 2 - size / 2, width: size, height: size,
      opacity: a.opacity, transformOrigin: "50% 50%", transform: `rotate(${a.rotate}deg) scaleY(${a.squash})`,
    }}>
      <Portal strength={a.portal} width={a.height} />
      <svg viewBox={`${-LIPA_VB} ${-LIPA_VB} ${LIPA_VB * 2} ${LIPA_VB * 2}`} width={size} height={size} style={{ overflow: "visible" }}>
        <Lipa pose={lipa.pose} expression={lipa.expression} t={secs + ctx.seed * 0.07} facing={facing} uid={uid}
          flapTip={lipa.flapTip} bob={lipa.bob} />
      </svg>
    </div>
  );
};

const GraphicLayer: React.FC<{ g: PlanGraphic; frame: number; focus: boolean; fps: number; place: Placement }> = ({
  g, frame, focus, fps, place,
}) => {
  if (frame < g.start_frame || frame >= g.end_frame) return null;
  const t = frame - g.start_frame;
  const len = g.end_frame - g.start_frame;
  const fade = Math.min(1, t / 8, (len - t) / 8);
  // Focus shots frame the graphic large in the centre; otherwise collision-aware placement
  // (scene/placement.ts) keeps panels off the characters.
  const style: React.CSSProperties = focus
    ? { left: "50%", top: "47%", translate: "-50% -50%", scale: "1.15" }
    : { left: place.left, top: place.top, scale: String(place.scale), transformOrigin: "0 0" };
  const shown = place.layout ? { ...g, props: { ...g.props, layout: place.layout } } : g;
  return (
    <div style={{ position: "absolute", opacity: Math.max(0, fade), ...style }}>
      <GraphicView g={shown} t={t} len={len} fps={fps} />
    </div>
  );
};

/** Characters' on-screen boxes for a shot (rest positions through the opening camera). */
const characterBoxes = (actors: ActorState[], depths: PlanShot["blocking"][number]["depth"][], cam: CameraState): Box[] =>
  actors.map((a, i) => {
    const k = DEPTH_PARALLAX[depths[i] ?? "midground"];
    const zoom = 1 + (cam.zoom - 1) * k;
    const cx = W / 2 + (cam.cx - W / 2) * k;
    const cy = H / 2 + (cam.cy - H / 2) * k;
    const sx = (x: number) => (x - cx) * zoom + W / 2;
    const sy = (y: number) => (y - cy) * zoom + H / 2;
    if (a.character === "arka") {
      const w = a.height * 0.62;
      return { x0: sx(a.x - w / 2), x1: sx(a.x + w / 2), y0: sy(a.y - a.height * 1.03), y1: sy(a.y) };
    }
    const r = a.height * 0.7;
    const c = a.y - a.height / 2;
    return { x0: sx(a.x - r), x1: sx(a.x + r), y0: sy(c - r), y1: sy(c + r) };
  });

export const Scene: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shot = shotAt(scene, frame);
  const t = frame - shot.start_frame;
  const len = shot.end_frame - shot.start_frame;

  const seedOf = (i: number) => i * 17 + scene.scene_id.length;
  const actors = shot.blocking.map((b, i) => actorAt(b, t, len, seedOf(i)));
  const shotIndex = scene.shots.indexOf(shot);
  const prevShot = scene.shots[shotIndex - 1];
  // Distance Arka walks along his facing, per frame, in rig units: drives a stride-synced gait.
  const travel = useMemo(() => scene.shots.map((sh) => sh.blocking.map((b, i) => {
    if (b.character !== "arka" || (b.motion !== "walk" && b.motion !== "run")) return undefined;
    const n = Math.max(1, sh.end_frame - sh.start_frame);
    const dir = b.facing === "left" ? -1 : 1;
    const out = [0];
    let last = actorAt(b, 0, n, i * 17 + scene.scene_id.length);
    for (let f = 1; f < n; f++) {
      const cur = actorAt(b, f, n, i * 17 + scene.scene_id.length);
      out.push(out[f - 1] + ((cur.x - last.x) * dir) / (Math.max(cur.height, 1) / ARKA_UNITS));
      last = cur;
    }
    return out;
  })), [scene]);
  const velOf = (i: number) => {
    const a = actorAt(shot.blocking[i], t, len, seedOf(i));
    const b = actorAt(shot.blocking[i], Math.max(0, t - 2), len, seedOf(i));
    return { x: (a.x - b.x) / 2, y: (a.y - b.y) / 2 };
  };
  // Camera framing reference: where characters stand (start and end of their paths),
  // ignoring entrances/exits and motion wobble, so a static camera frames the action.
  const rest = (b: PlanShot["blocking"][number]) => ({ ...b, enter: "none" as const, exit: "none" as const, motion: "none" as const });
  const actorsStart = shot.blocking.flatMap((b) => [actorAt(rest(b), 0, len, 0), actorAt(rest(b), len - 1, len, 0)]);
  const cam = cameraAt(shot, t, actors, actorsStart);
  const boost = transitionCameraBoost(frame, scene.duration_frames, scene.transition_in, scene.transition_out);

  // Where the characters stand on screen in this shot -> graphics go where they cover no one.
  // Decided once per shot (rest positions, opening camera) so panels never jump mid-shot.
  const camStart = cameraAt(shot, 0, actorsStart, actorsStart);
  const boxes = characterBoxes(actorsStart, shot.blocking.flatMap((b) => [b.depth, b.depth]), camStart)
    .filter((b) => b.x1 > 0 && b.x0 < W && b.y1 > 0 && b.y0 < H);
  let labelIndex = 0;
  const places = scene.graphics.map((g) => placeGraphic(g.component, boxes, g.component === "Label" ? labelIndex++ : 0));

  const speaking = scene.lines.find((l) => frame >= l.start_frame && frame < l.end_frame);
  const mouthFor = (who: string) =>
    speaking && speaking.speaker === who ? speaking.mouth[frame - speaking.start_frame] ?? 0 : 0;

  const props = scene.props ?? [];
  const propsAt = (depth: PlanProp["depth"]) => {
    const list = props.filter((p) => p.depth === depth);
    return list.length ? (
      <PropLayer>{list.map((p, i) => <PropView key={i} p={p} f={frame} />)}</PropLayer>
    ) : null;
  };
  const layer = (name: Layer) => (
    <AbsoluteFill style={{ transform: worldTransform(cam, LAYER_PARALLAX[name], boost), transformOrigin: "0 0" }}>
      <BackgroundLayer theme={scene.theme} layer={name} frame={frame} />
      {propsAt(name)}
    </AbsoluteFill>
  );

  const byDepth = (depth: "background" | "midground" | "foreground") => (
    <AbsoluteFill style={{ transform: worldTransform(cam, DEPTH_PARALLAX[depth], boost), transformOrigin: "0 0" }}>
      {shot.blocking.map((b, i) => b.depth === depth && (
        <Actor key={b.character} a={actors[i]} t={t} frame={frame} mouth={mouthFor(b.character)}
          ctx={{
            b, len, fps, seed: seedOf(i), talking: speaking?.speaker === b.character,
            travel: travel[shotIndex]?.[i], vel: b.character === "lipa" ? velOf(i) : undefined,
            prev: prevShot?.blocking.find((p) => p.character === b.character),
          }} />
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
      {props.some((p) => p.depth === "front") && (
        <AbsoluteFill style={{ transform: worldTransform(cam, DEPTH_PARALLAX.foreground, boost), transformOrigin: "0 0" }}>
          {propsAt("front")}
        </AbsoluteFill>
      )}
      {scene.graphics.map((g, i) => (
        <GraphicLayer key={i} g={g} frame={frame} fps={fps} place={places[i]}
          focus={shot.focus === "graphic" || shot.shot_type === "insert"} />
      ))}
      <Captions captions={scene.captions ?? []} frame={frame} />
      <SceneTransitions frame={frame} duration={scene.duration_frames} tin={scene.transition_in} tout={scene.transition_out} />
    </AbsoluteFill>
  );
};
