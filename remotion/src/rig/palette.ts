// Arka & Lipa — rig.v1 palette (single source of truth for rig, board and video)
export const C = {
  ink: "#2B2240",
  navy: "#24305E",
  navyDeep: "#1A2348",

  scarf: "#2E9E7F",
  scarfDark: "#1F7A61",
  scarfLight: "#62C7A6",

  hat: "#F4EBD6",
  hatShade: "#DCCBA8",
  band: "#8B5A34",
  leaf: "#5DB25C",
  leafDark: "#3D8A47",
  flower: "#F26B4C",
  flowerCore: "#FFD25E",

  skin: "#F7D2AE",
  skinShade: "#E9B08A",
  blush: "#F2907B",

  hair: "#C98A3D",
  hairShade: "#A2672A",
  hairLight: "#EDC074",
  brow: "#5A3216",

  iris: "#E59A2B",
  irisDark: "#9C560F",
  irisLight: "#FFD47E",
  pupil: "#3A2416",
  sclera: "#FFFFFF",

  shirt: "#FBF7EE",
  shirtShade: "#E3DACA",

  pack: "#9A6438",
  packDark: "#744723",
  packLight: "#B98251",
  strap: "#6E4322",
  bedroll: "#3F7FC6",
  bedrollDark: "#2D5E98",

  shorts: "#B99B6B",
  shortsShade: "#977A4E",

  sock: "#FFFFFF",
  shoe: "#F26B4C",
  shoeDark: "#C9502F",
  sole: "#F4EBD6",

  brass: "#D2A040",
  brassDark: "#A6772A",
  brassLight: "#F4D682",

  paper: "#F3E4C0",
  paperMid: "#E7D0A0",
  paperDark: "#CDAE76",
  paperLine: "#B58F62",
  route: "#E85C3F",
  water: "#4E92D6",
  land: "#9CCB7A",

  mouth: "#8E2F3A",
  tongue: "#F27C6E",
  teeth: "#FFFFFF",

  glow: "#FFD872",
  bg: "#F5EFE3",
  card: "#FFFDF8",
  topo: "#E6DCC8",
} as const;

// Swatches shown on the character bible
export const SWATCHES: { name: string; hex: string }[] = [
  { name: "Ink Plum", hex: C.ink },
  { name: "Explorer Navy", hex: C.navy },
  { name: "Scarf Teal", hex: C.scarf },
  { name: "Sunhat Cream", hex: C.hat },
  { name: "Honey Hair", hex: C.hair },
  { name: "Amber Iris", hex: C.iris },
  { name: "Skin", hex: C.skin },
  { name: "Satchel Brown", hex: C.pack },
  { name: "Trail Khaki", hex: C.shorts },
  { name: "Ember Coral", hex: C.shoe },
  { name: "River Blue", hex: C.bedroll },
  { name: "Map Parchment", hex: C.paper },
  { name: "Compass Brass", hex: C.brass },
  { name: "Lantern Glow", hex: C.glow },
];
