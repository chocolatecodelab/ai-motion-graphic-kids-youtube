import { Config } from "@remotion/cli/config";

// CLI / Studio only. The Python pipeline renders through render-server.mjs (Node API),
// which does not read this file: its render settings are explicit there.
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setColorSpace("bt709");
