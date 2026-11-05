// Motion-graphics components (config/catalogue/components.yaml). Screen-space overlays.
// Accuracy rule: when `illustrative` is true, no numbers, axes or units are drawn.
import React from "react";
import { Easing, interpolate, spring } from "remotion";
import { C, FONT_BODY, FONT_TITLE } from "../brand";
import type { PlanGraphic } from "../types";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

interface GP { g: PlanGraphic; t: number; len: number; fps: number }

const str = (v: unknown, d = "") => (typeof v === "string" ? v : typeof v === "number" ? String(v) : d);
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const obj = (v: unknown): Record<string, unknown> => (v && typeof v === "object" ? (v as Record<string, unknown>) : {});
const num = (v: unknown, d = 1) => (typeof v === "number" && isFinite(v) ? v : d);

const COLOR: Record<string, string> = {
  red: "#FF5A5A", orange: C.orange, yellow: C.yellow, green: "#5BCB6B", blue: "#3D8BFF",
  violet: "#8B5CF6", purple: "#8B5CF6", white: "#FFFFFF", teal: C.teal,
};
const colorOf = (v: unknown, i = 0) => {
  const s = str(v).toLowerCase();
  const named = Object.keys(COLOR).find((k) => s.includes(k)); // "Violet in sunlight" -> violet
  return COLOR[s] ?? (named ? COLOR[named] : Object.values(COLOR)[i % 6]);
};

const Panel: React.FC<{ children: React.ReactNode; title?: string; width?: number }> = ({ children, title, width = 760 }) => (
  <div style={{
    width, padding: "26px 32px", borderRadius: 28, background: "rgba(244,240,232,0.94)",
    boxShadow: "0 12px 40px rgba(0,0,0,0.25)", border: `6px solid ${C.blue}`, fontFamily: FONT_BODY, color: C.ink,
  }}>
    {title && <div style={{ fontFamily: FONT_TITLE, fontSize: 52, color: C.blue, marginBottom: 12, lineHeight: 1.05 }}>{title}</div>}
    {children}
  </div>
);

const LightRays: React.FC<GP> = ({ g, t }) => {
  const mode = str(g.props.mode, "split");
  const colors = arr(g.props.colors).map((c, i) => colorOf(c, i));
  const grow = interpolate(t, [0, 24], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <svg width={900} height={520} viewBox="0 0 900 520">
      <rect x={0} y={0} width={900} height={520} rx={36} fill="rgba(15,30,69,0.82)" />
      {mode === "split" && (
        <g>
          <path d={`M40 260 L${40 + 300 * grow} 260`} stroke="#FFFFFF" strokeWidth={26} strokeLinecap="round" />
          {colors.map((c, i) => {
            const a = ((i - (colors.length - 1) / 2) * 9 * Math.PI) / 180;
            const len = 480 * interpolate(t, [18, 44], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
            return <path key={i} d={`M340 260 L${340 + Math.cos(a) * len} ${260 + Math.sin(a) * len}`} stroke={c} strokeWidth={16} strokeLinecap="round" />;
          })}
          <polygon points="300,200 380,260 300,320" fill="rgba(255,255,255,0.35)" />
        </g>
      )}
      {mode !== "split" && (
        <g>
          {/* the air the light travels through: small molecules */}
          {Array.from({ length: 22 }, (_, k) => (
            <circle key={`m${k}`} cx={60 + ((k * 137) % 780) + Math.sin(t / 9 + k) * 6}
              cy={60 + ((k * 89) % 400) + Math.cos(t / 11 + k) * 6} r={9} fill={C.cream} opacity={0.35} />
          ))}
          {/* waves travel left -> right on a loop; in scatter mode short (blue/violet) light
              bursts off the air molecule in every direction while long (red) light passes by */}
          {colors.map((c, i) => {
            const scatter = mode === "scatter" && /#3D8BFF|#8B5CF6/i.test(c);
            const lane = colors.length > 1 ? 150 + (i * 220) / (colors.length - 1) : 260;
            const x = ((t * 14 + i * 230) % 1300) - 260;
            if (!scatter) {
              return <path key={i} d={`M${x} ${lane} q 35 -30 70 0 t 70 0 t 70 0 t 70 0`} stroke={c}
                strokeWidth={12} fill="none" strokeLinecap="round" />;
            }
            return (
              <g key={i}>
                <path d={`M${Math.min(x, 330)} 260 q 18 -22 36 0 t 36 0 t 36 0`} stroke={c} strokeWidth={12} fill="none"
                  strokeLinecap="round" opacity={x < 330 ? 1 : 0.25} />
                {Array.from({ length: 12 }, (_, k) => {
                  const ang = (k / 12) * Math.PI * 2;
                  const r = interpolate((t * 1.4 + k * 4) % 48, [0, 48], [20, 320]);
                  return <circle key={k} cx={450 + Math.cos(ang) * r} cy={260 + Math.sin(ang) * r * 0.75} r={14}
                    fill={c} opacity={Math.max(0, 1 - r / 330)} />;
                })}
              </g>
            );
          })}
          {mode === "scatter" && <circle cx={450} cy={260} r={30} fill={C.cream} stroke={C.teal} strokeWidth={6} />}
        </g>
      )}
    </svg>
  );
};

const WaveCompare: React.FC<GP> = ({ g, t }) => {
  const waves = arr(g.props.waves).map(obj);
  return (
    <Panel title="Waves">
      {waves.map((w, i) => {
        const rel = num(w.wavelength_rel, 1 + i * 0.6);
        const len = 70 * rel;
        const phase = t * 6;
        const d = Array.from({ length: 121 }, (_, k) => {
          const x = k * 5;
          return `${k ? "L" : "M"}${x} ${40 + Math.sin(((x + phase) / len) * Math.PI * 2) * 30}`;
        }).join(" ");
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, margin: "8px 0",
            opacity: interpolate(t, [i * 10, i * 10 + 12], [0, 1], clamp) }}>
            <div style={{ width: 150, fontSize: 40, fontWeight: 800, color: colorOf(w.color, i) }}>{str(w.label, `Wave ${i + 1}`)}</div>
            <svg width={600} height={80}><path d={d} stroke={colorOf(w.color, i)} strokeWidth={8} fill="none" strokeLinecap="round" /></svg>
          </div>
        );
      })}
    </Panel>
  );
};

const ScaleCompare: React.FC<GP> = ({ g, t, fps }) => {
  const items = arr(g.props.items).map(obj);
  const maxRel = Math.max(...items.map((it) => num(it.relative_size, 1)), 1);
  return (
    <Panel title={str(g.props.title, "Size")}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 40, height: 340 }}>
        {items.map((it, i) => {
          const rel = num(it.relative_size, 1);
          const size = Math.max(14, 300 * Math.sqrt(rel / maxRel));
          const s = spring({ frame: t - i * 8, fps, config: { damping: 14 } });
          return (
            <div key={i} style={{ textAlign: "center" }}>
              <div style={{ width: size, height: size, borderRadius: "50%", background: i ? C.yellow : C.teal,
                scale: String(s), margin: "0 auto", border: `5px solid ${C.blue}` }} />
              <div style={{ fontSize: 38, fontWeight: 800, marginTop: 10 }}>{str(it.label)}</div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
};

const BarGrow: React.FC<GP> = ({ g, t }) => {
  const items = arr(g.props.items).map(obj);
  const max = Math.max(...items.map((it) => num(it.value, 1)), 1);
  return (
    <Panel title={str(g.props.title, "")}>
      {items.map((it, i) => {
        const v = num(it.value, 1);
        const w = interpolate(t, [i * 8, i * 8 + 26], [0, (v / max) * 440], { ...clamp, easing: Easing.out(Easing.cubic) });
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, margin: "14px 0" }}>
            <div style={{ width: 300, fontSize: 46, fontWeight: 800, lineHeight: 1.05 }}>{str(it.label)}</div>
            <div style={{ height: 58, width: w, borderRadius: 29, background: colorOf(it.color ?? it.label, i) }} />
            {!g.illustrative && <div style={{ fontSize: 46, fontWeight: 800 }}>{str(it.value)}</div>}
          </div>
        );
      })}
    </Panel>
  );
};

const Label: React.FC<GP> = ({ g, t, fps }) => {
  const s = spring({ frame: t, fps, config: { damping: 12 } });
  return (
    <div style={{ scale: String(s), padding: "14px 30px", borderRadius: 999, background: C.yellow,
      border: `5px solid ${C.blue}`, fontFamily: FONT_TITLE, fontSize: 58, color: C.blue,
      boxShadow: "0 8px 24px rgba(0,0,0,0.25)" }}>
      {str(g.props.text)}
    </div>
  );
};

const HologramPanel: React.FC<GP> = ({ g, t }) => {
  const items = arr(g.props.items).map((x) => str(x));
  const scan = (t * 6) % 420;
  return (
    <div style={{ width: 760, padding: 30, borderRadius: 26, background: "rgba(85,187,165,0.28)",
      border: `4px solid ${C.teal}`, boxShadow: `0 0 40px ${C.teal}`, fontFamily: FONT_BODY, color: C.white, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: scan, height: 6, background: "rgba(255,255,255,0.35)" }} />
      <div style={{ fontFamily: FONT_TITLE, fontSize: 52, marginBottom: 14 }}>{str(g.props.title)}</div>
      {items.map((it, i) => (
        <div key={i} style={{ fontSize: 40, fontWeight: 700, margin: "8px 0",
          opacity: interpolate(t, [10 + i * 12, 22 + i * 12], [0, 1], clamp),
          translate: `${interpolate(t, [10 + i * 12, 22 + i * 12], [40, 0], clamp)}px 0px` }}>
          ✦ {it}
        </div>
      ))}
    </div>
  );
};

const Recap: React.FC<GP> = ({ g, t, fps }) => {
  const points = arr(g.props.points).map((x) => str(x));
  return (
    <div style={{ display: "flex", flexDirection: g.props.layout === "column" ? "column" : "row", gap: 26 }}>
      {points.map((p, i) => {
        const s = spring({ frame: t - i * 18, fps, config: { damping: 14 } });
        return (
          <div key={i} style={{ width: 380, minHeight: 300, padding: 26, borderRadius: 30, background: C.cream,
            border: `6px solid ${[C.teal, C.blue, C.orange][i % 3]}`, scale: String(s),
            fontFamily: FONT_BODY, color: C.ink, boxShadow: "0 10px 30px rgba(0,0,0,0.22)" }}>
            <div style={{ fontFamily: FONT_TITLE, fontSize: 70, color: [C.teal, C.blue, C.orange][i % 3] }}>{i + 1}</div>
            <div style={{ fontSize: 40, fontWeight: 800, lineHeight: 1.15 }}>{p}</div>
          </div>
        );
      })}
    </div>
  );
};

const Counter: React.FC<GP> = ({ g, t }) => {
  const to = num(g.props.to, 0);
  const from = num(g.props.from, 0);
  const v = interpolate(t, [0, 40], [from, to], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <Panel>
      <div style={{ fontFamily: FONT_TITLE, fontSize: 120, color: C.blue, textAlign: "center" }}>
        {g.illustrative ? "↑" : `${Math.round(v).toLocaleString("en-US")} ${str(g.props.unit)}`}
      </div>
    </Panel>
  );
};

const Orbit: React.FC<GP> = ({ g, t }) => {
  const bodies = arr(g.props.bodies).map((x) => str(x));
  return (
    <svg width={720} height={520} viewBox="-360 -260 720 520">
      <circle r={70} fill={C.yellow} />
      <text y={12} textAnchor="middle" fontFamily={FONT_BODY} fontSize={34} fontWeight={800} fill={C.blue}>{str(g.props.center)}</text>
      {bodies.map((b, i) => {
        const r = 140 + i * 70;
        const a = t / (30 + i * 14) + i;
        return (
          <g key={i}>
            <ellipse rx={r} ry={r * 0.6} fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth={3} strokeDasharray="10 10" />
            <circle cx={Math.cos(a) * r} cy={Math.sin(a) * r * 0.6} r={26} fill={C.teal} />
            <text x={Math.cos(a) * r} y={Math.sin(a) * r * 0.6 - 36} textAnchor="middle" fontFamily={FONT_BODY} fontSize={30} fontWeight={800} fill={C.white}>{b}</text>
          </g>
        );
      })}
    </svg>
  );
};

const ListCard: React.FC<GP & { title: string; items: string[] }> = ({ t, title, items }) => (
  <Panel title={title}>
    {items.map((it, i) => (
      <div key={i} style={{ fontSize: 38, fontWeight: 700, margin: "6px 0",
        opacity: interpolate(t, [i * 10, i * 10 + 12], [0, 1], clamp) }}>• {it}</div>
    ))}
  </Panel>
);

export const GraphicView: React.FC<GP> = (p) => {
  const g = p.g;
  switch (g.component) {
    case "LightRays": return <LightRays {...p} />;
    case "WaveCompare": return <WaveCompare {...p} />;
    case "ScaleCompare": return <ScaleCompare {...p} />;
    case "BarGrow": return <BarGrow {...p} />;
    case "Label": return <Label {...p} />;
    case "HologramPanel": return <HologramPanel {...p} />;
    case "Recap": return <Recap {...p} />;
    case "Counter": return <Counter {...p} />;
    case "Orbit": return <Orbit {...p} />;
    case "Timeline": return <ListCard {...p} title="Timeline" items={arr(g.props.events).map((e) => str(obj(e).label, str(e)))} />;
    case "Cutaway": return <ListCard {...p} title={str(g.props.subject, "Inside")} items={arr(g.props.layers).map((x) => str(x))} />;
    case "ExplodedView": return <ListCard {...p} title={str(g.props.subject, "Parts")} items={arr(g.props.parts).map((x) => str(x))} />;
    default: return <ListCard {...p} title={g.component} items={[]} />;
  }
};
