import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const C = {
  blue: "#243B75",
  yellow: "#F8C84A",
  orange: "#F47C45",
  teal: "#55BBA5",
  cream: "#F4F0E8",
  ink: "#1D2B4F",
  white: "#FFFFFF",
  brass: "#C99A3B",
  skin: "#C68A63",
  skinShade: "#A86E4B",
  hair: "#2B1F1A",
};

export const FONT_TITLE = "Lilita One";
// Family name must not end in a bare digit token ("Baloo 2" is invalid unquoted CSS),
// otherwise the browser silently falls back to a serif font.
export const FONT_BODY = "BalooTwo";

// OFL fonts shipped in public/fonts (licence files alongside).
export const fontsReady = Promise.all([
  loadFont({ family: FONT_TITLE, url: staticFile("fonts/LilitaOne-Regular.ttf"), weight: "400" }),
  loadFont({ family: FONT_BODY, url: staticFile("fonts/Baloo2-Variable.ttf"), weight: "400 800" }),
]);
