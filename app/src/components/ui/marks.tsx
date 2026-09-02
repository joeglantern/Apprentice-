/** The two identity marks, drawn rather than rastered so they recolour and stay
 * sharp at every size they appear at (15px chat attribution up to 76px onboarding).
 *
 * Geometry is measured off the handoff's rasters (assets/brand) rather than eyeballed:
 * every number below is the reference mark's own, normalised to a 24 grid and
 * re-centred (the app-icon composition sits its mark slightly right of the tile
 * centre, which is a tile decision, not the mark's). */

import Svg, { Circle, Defs, G, Mask, Rect } from "react-native-svg";

/** Umbra: two concentric squircles. Rail (36), auth (44), anywhere the app signs itself. */
export function UmbraMark({ size = 36, color = "#F2F2EF" }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Rect x={5.55} y={5.55} width={12.9} height={12.9} rx={4.55} stroke={color} strokeWidth={1.2} fill="none" />
      <Rect x={7.95} y={7.95} width={8.1} height={8.1} rx={2.55} stroke={color} strokeWidth={1.1} fill="none" />
    </Svg>
  );
}

/** Eidolon: a ring and three echoes trailing right, each stroke thinner than the
 * last. The model's own signature, so it carries the accent. The mask is what makes
 * the echoes read as *behind* the front ring without painting an opaque backdrop. */
export function EidolonMark({ size = 20, color = "#57E8C8" }: { size?: number; color?: string }) {
  const R = 7.11;
  const FRONT = 8.58;
  const echoes: [number, number][] = [
    [11.31, 0.84],
    [13.65, 0.72],
    [15.75, 0.6],
  ];

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Defs>
        <Mask id="eidolon-behind">
          <Rect x="0" y="0" width="24" height="24" fill="#fff" />
          <Circle cx={FRONT} cy={12} r={R + 0.6} fill="#000" />
        </Mask>
      </Defs>
      <G mask="url(#eidolon-behind)">
        {echoes.map(([cx, sw]) => (
          <Circle key={cx} cx={cx} cy={12} r={R} stroke={color} strokeWidth={sw} fill="none" />
        ))}
      </G>
      <Circle cx={FRONT} cy={12} r={R} stroke={color} strokeWidth={1.2} fill="none" />
    </Svg>
  );
}
