// Scene backgrounds: the M2 SVG scene library (scene/bg). Each theme is drawn in 3 parallax
// layers in world coordinates that extend well past the frame, so wide shots, pans and
// zoom-outs never show an edge. Unknown themes fall back to the neutral studio.
import React from "react";
import type { Theme } from "../types";
import { THEMES, type BgLayer } from "./bg/themes";

export type Layer = BgLayer;
export const LAYER_PARALLAX: Record<Layer, number> = { far: 0.35, mid: 0.7, near: 1 };

export const BackgroundLayer: React.FC<{ theme: Theme; layer: Layer; frame: number }> = ({ theme, layer, frame }) =>
  (THEMES[theme as keyof typeof THEMES] ?? THEMES.studio)(layer, frame);