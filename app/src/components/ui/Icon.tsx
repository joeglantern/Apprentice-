/** The 24 approved UI glyphs, drawn as SVG rather than shipped as the handoff's
 * reference PNGs: they recolour with the theme, stay sharp at any density, and
 * cost nothing in the bundle. Lucide geometry on a 24 grid, 1.5 stroke per the
 * design system. Nav mapping (handoff): compass=explore, plusSquare=create,
 * chat=chat, swatches=brand kits, list=jobs, sliders=settings. */

import Svg, { Circle, Path, Polyline, Rect } from "react-native-svg";

export type IconName =
  | "alert"
  | "arrowLeft"
  | "arrowUp"
  | "chat"
  | "check"
  | "clock"
  | "compass"
  | "download"
  | "eye"
  | "folder"
  | "grid"
  | "image"
  | "layers"
  | "list"
  | "pencil"
  | "plusSquare"
  | "refresh"
  | "search"
  | "share"
  | "sliders"
  | "star"
  | "swatches"
  | "trash"
  | "type";

interface Props {
  name: IconName;
  size?: number;
  color?: string;
  /** The design system's default weight. Heavier only for very small sizes. */
  strokeWidth?: number;
  opacity?: number;
}

export function Icon({ name, size = 20, color = "#F2F2EF", strokeWidth = 1.5, opacity = 1 }: Props) {
  const s = { stroke: color, strokeWidth, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill: "none" };

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" opacity={opacity}>
      {name === "alert" && (
        <>
          <Path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" {...s} />
          <Path d="M12 9v4" {...s} />
          <Path d="M12 17h.01" {...s} />
        </>
      )}
      {name === "arrowLeft" && (
        <>
          <Path d="M19 12H5" {...s} />
          <Path d="m12 19-7-7 7-7" {...s} />
        </>
      )}
      {name === "arrowUp" && (
        <>
          <Path d="M12 19V5" {...s} />
          <Path d="m5 12 7-7 7 7" {...s} />
        </>
      )}
      {name === "chat" && (
        <Path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" {...s} />
      )}
      {name === "check" && <Path d="M20 6 9 17l-5-5" {...s} />}
      {name === "clock" && (
        <>
          <Circle cx="12" cy="12" r="10" {...s} />
          <Polyline points="12 6 12 12 16 14" {...s} />
        </>
      )}
      {name === "compass" && (
        <>
          <Circle cx="12" cy="12" r="10" {...s} />
          <Path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36z" {...s} />
        </>
      )}
      {name === "download" && (
        <>
          <Path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" {...s} />
          <Polyline points="7 10 12 15 17 10" {...s} />
          <Path d="M12 15V3" {...s} />
        </>
      )}
      {name === "eye" && (
        <>
          <Path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0" {...s} />
          <Circle cx="12" cy="12" r="3" {...s} />
        </>
      )}
      {name === "folder" && (
        <Path
          d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"
          {...s}
        />
      )}
      {name === "grid" && (
        <>
          <Rect x="3" y="3" width="7" height="7" rx="1" {...s} />
          <Rect x="14" y="3" width="7" height="7" rx="1" {...s} />
          <Rect x="14" y="14" width="7" height="7" rx="1" {...s} />
          <Rect x="3" y="14" width="7" height="7" rx="1" {...s} />
        </>
      )}
      {name === "image" && (
        <>
          <Rect x="3" y="3" width="18" height="18" rx="2" {...s} />
          <Circle cx="9" cy="9" r="2" {...s} />
          <Path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21" {...s} />
        </>
      )}
      {name === "layers" && (
        <>
          <Path
            d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"
            {...s}
          />
          <Path d="m6.08 9.5-3.5 1.6a1 1 0 0 0 0 1.81l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9a1 1 0 0 0 0-1.83l-3.5-1.59" {...s} />
          <Path d="m6.08 14.5-3.5 1.6a1 1 0 0 0 0 1.81l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9a1 1 0 0 0 0-1.83l-3.5-1.59" {...s} />
        </>
      )}
      {name === "list" && (
        <>
          <Path d="M8 6h13" {...s} />
          <Path d="M8 12h13" {...s} />
          <Path d="M8 18h13" {...s} />
          <Path d="M3 6h.01" {...s} />
          <Path d="M3 12h.01" {...s} />
          <Path d="M3 18h.01" {...s} />
        </>
      )}
      {name === "pencil" && (
        <>
          <Path
            d="M21.17 6.81a1 1 0 0 0-3.98-3.99L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.63l4.35-1.32a2 2 0 0 0 .83-.5Z"
            {...s}
          />
          <Path d="m15 5 4 4" {...s} />
        </>
      )}
      {name === "plusSquare" && (
        <>
          <Rect x="3" y="3" width="18" height="18" rx="2" {...s} />
          <Path d="M9 12h6" {...s} />
          <Path d="M12 9v6" {...s} />
        </>
      )}
      {name === "refresh" && (
        <>
          <Path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" {...s} />
          <Path d="M21 3v5h-5" {...s} />
          <Path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" {...s} />
          <Path d="M8 16H3v5" {...s} />
        </>
      )}
      {name === "search" && (
        <>
          <Circle cx="11" cy="11" r="8" {...s} />
          <Path d="m21 21-4.3-4.3" {...s} />
        </>
      )}
      {name === "share" && (
        <>
          <Circle cx="18" cy="5" r="3" {...s} />
          <Circle cx="6" cy="12" r="3" {...s} />
          <Circle cx="18" cy="19" r="3" {...s} />
          <Path d="m8.59 13.51 6.83 3.98" {...s} />
          <Path d="m15.41 6.51-6.82 3.98" {...s} />
        </>
      )}
      {name === "sliders" && (
        <>
          <Path d="M21 4h-7" {...s} />
          <Path d="M10 4H3" {...s} />
          <Path d="M21 12h-9" {...s} />
          <Path d="M8 12H3" {...s} />
          <Path d="M21 20h-5" {...s} />
          <Path d="M12 20H3" {...s} />
          <Path d="M14 2v4" {...s} />
          <Path d="M8 10v4" {...s} />
          <Path d="M16 18v4" {...s} />
        </>
      )}
      {name === "star" && (
        <Path
          d="M11.53 2.3a.53.53 0 0 1 .95 0l2.3 4.68a2.12 2.12 0 0 0 1.6 1.16l5.17.75a.53.53 0 0 1 .29.91l-3.73 3.63a2.12 2.12 0 0 0-.61 1.88l.88 5.14a.53.53 0 0 1-.77.56l-4.62-2.43a2.12 2.12 0 0 0-1.97 0L6.4 21.01a.53.53 0 0 1-.77-.56l.88-5.14a2.12 2.12 0 0 0-.61-1.88L2.16 9.8a.53.53 0 0 1 .29-.91l5.17-.75a2.12 2.12 0 0 0 1.6-1.16z"
          {...s}
        />
      )}
      {/* Overlapping colour chips - brand kits are read as a stack of swatches. */}
      {name === "swatches" && (
        <>
          <Rect x="3" y="3" width="12" height="12" rx="2.5" {...s} />
          <Path d="M9 21h9.5A2.5 2.5 0 0 0 21 18.5V9" {...s} />
          <Path d="M6 18h9.5a2.5 2.5 0 0 0 2.5-2.5V6" {...s} />
        </>
      )}
      {name === "trash" && (
        <>
          <Path d="M3 6h18" {...s} />
          <Path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" {...s} />
          <Path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" {...s} />
          <Path d="M10 11v6" {...s} />
          <Path d="M14 11v6" {...s} />
        </>
      )}
      {name === "type" && (
        <>
          <Polyline points="4 7 4 4 20 4 20 7" {...s} />
          <Path d="M9 20h6" {...s} />
          <Path d="M12 4v16" {...s} />
        </>
      )}
    </Svg>
  );
}
