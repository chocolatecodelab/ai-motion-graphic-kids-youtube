// Character Bible v2 reference sheet (docs/creative/CHARACTER_BIBLE.md): Arka & Lipa,
// rendered from the same production rig the scenes use (src/rig).
import React from "react";
import { AbsoluteFill } from "remotion";
import { Board } from "./board/Board";

export { BOARD_H as SHEET_H, BOARD_W as SHEET_W } from "./board/Board";

export const CharacterSheet: React.FC = () => (
  <AbsoluteFill>
    <Board />
  </AbsoluteFill>
);
