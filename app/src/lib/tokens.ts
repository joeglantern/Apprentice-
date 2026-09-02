// Umbra design tokens - build-order item 1. Mirrors "Umbra v2.dc.html" exactly.
// Themes: "space" (default, space black) and "graphite" (softer dark).

export const themes = {
  space: {
    bg0: "#060607",      // app background
    void: "#050506",     // create stage, rail, media surrounds
    sf0: "#0C0C0E",      // sunken surface (inputs, queued rows)
    sf: "#121214",       // surface (cards, deck)
    raise: "#1B1B1E",    // raised surface (active nav, bubbles)
    raise2: "#242428",   // raised hover / deck border
    ln: "#18181B",       // hairline
    ln2: "#26262A",      // hairline strong
    ln3: "#3E3E44",      // hairline hover
    t1: "#F2F2EF",       // text primary (warm off white)
    t2: "#9C9CA3",       // text secondary
    t3: "#67676E",       // text muted
    t4: "#4C4C52",       // text faint (mono metadata)
    accent: "#57E8C8",   // electric mint - actions and progress ONLY
    accentH: "#6FF0D2",  // accent hover
    success: "#4ADE80",
    error: "#F87171",
    mediaBg: "#000000",  // OLED media view only
  },
  graphite: {
    bg0: "#141417", void: "#111114", sf0: "#1A1A1E", sf: "#1E1E22",
    raise: "#28282D", raise2: "#313137", ln: "#26262B", ln2: "#333339", ln3: "#45454C",
    t1: "#F4F4F1", t2: "#A6A6AD", t3: "#7A7A82", t4: "#5C5C64",
    accent: "#57E8C8", accentH: "#6FF0D2", success: "#4ADE80", error: "#F87171", mediaBg: "#000000",
  },
} as const;

// Accent alternatives (one at a time): mint #57E8C8 (default),
// coral #FF6B4A, lime #E8FF47, amber #FFC53D.

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 44 } as const;

export const radii = {
  chip: 999, control: 10, card: 14, media: 12, mediaLg: 16, deck: 18, navItem: 14, thumb: 9,
} as const;

export const type = {
  display: { family: "SpaceGrotesk", tracking: -0.03 },   // lowercase screen titles
  displayXL: 64, displayLG: 44, displayMD: 30,
  body: { family: "Inter" },
  bodyMD: 14, bodySM: 13.5, bodyXS: 12,
  mono: { family: "JetBrainsMono" },                       // ids, seeds, section labels
  monoMD: 12, monoSM: 10.5, monoXS: 9.5, monoLabelTracking: 1.2,
} as const;

export const motion = {
  press: 0.97,            // pressed scale (0.92-0.97 by size)
  fadeUpMs: 200,          // render arrival
  springMs: [150, 250],   // reanimated spring range
  scanLoopMs: 2200,       // denoising scanline sweep
  pulseLoopMs: 1600,      // active stage dot
} as const;

export const breakpoints = { phone: 0, tablet: 768, desktop: 1024 } as const;
export const contentMaxWidth = 1280;
export const grid = { phone: 2, smallDesktop: 3, desktop: 4, wide: 5 } as const; // explore columns

export type ThemeName = keyof typeof themes;
export type Palette = (typeof themes)[ThemeName];
