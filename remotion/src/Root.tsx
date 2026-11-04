import React from "react";
import { CalculateMetadataFunction, Composition, Still } from "remotion";
import { fontsReady } from "./brand";
import { CharacterSheet, SHEET_H, SHEET_W } from "./CharacterSheet";
import { RIG_CHECK_FRAMES, RigCheck } from "./RigCheck";
import { Scene } from "./scene/Scene";
import sample from "./sample-scene.json";
import type { PlanScene, SceneProps } from "./types";

void fontsReady;

const calculateMetadata: CalculateMetadataFunction<SceneProps> = ({ props }) => ({
  durationInFrames: Math.max(1, props.scene.duration_frames),
});

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Scene"
      component={Scene}
      durationInFrames={(sample as PlanScene).duration_frames}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ scene: sample as PlanScene }}
      calculateMetadata={calculateMetadata}
    />
    <Still id="CharacterSheet" component={CharacterSheet} width={SHEET_W} height={SHEET_H} />
    <Composition id="RigCheck" component={RigCheck} durationInFrames={RIG_CHECK_FRAMES} fps={30} width={1920} height={1080} />
  </>
);
