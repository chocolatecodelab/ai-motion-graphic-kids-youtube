import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import { fontsReady } from "./brand";
import { Scene } from "./scene/Scene";
import sample from "./sample-scene.json";
import type { PlanScene, SceneProps } from "./types";

void fontsReady;

const calculateMetadata: CalculateMetadataFunction<SceneProps> = ({ props }) => ({
  durationInFrames: Math.max(1, props.scene.duration_frames),
});

export const RemotionRoot: React.FC = () => (
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
);
