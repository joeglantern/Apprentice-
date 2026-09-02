import Svg, { Ellipse, G, Image as SvgImage, Path, Rect, Text as SvgText, TSpan } from "react-native-svg";

import { rasterUrl } from "@/lib/api";
import { ICON_PATHS } from "@/lib/icons";
import type { Layer } from "@/lib/types";

/** Greedy word wrap on a character budget. Explicit newlines always break. */
function wrap(text: string, charsPerLine: number): string[] {
  const out: string[] = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    for (const word of paragraph.split(/\s+/).filter(Boolean)) {
      const trial = line ? `${line} ${word}` : word;
      if (trial.length <= charsPerLine || !line) line = trial;
      else {
        out.push(line);
        line = word;
      }
    }
    out.push(line);
  }
  return out;
}

interface Props {
  jobId: string;
  layers: Layer[];
  canvasWidth: number;
  canvasHeight: number;
}

/** Renders the doc 01 section 3 layer JSON as SVG, vector structure with the style
 * model's raster fills composited inside it (doc 01 section 5, doc 04 section 3). The
 * viewBox is the coordinate system, so this is identical on web and on a phone. */
export function CanvasPreview({ jobId, layers, canvasWidth, canvasHeight }: Props) {
  const ordered = [...layers]
    .filter((l) => l.visible !== false)
    .sort((a, b) => a.z_index - b.z_index);

  return (
    // height is explicit: an Svg with only a width falls back to the SVG intrinsic
    // height of 150 instead of taking its aspect from the viewBox.
    <Svg width="100%" height="100%" viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
      {ordered.map((layer) => {
        const { x, y, width, height } = layer.bbox;
        if (layer.type === "icon" && layer.icon && ICON_PATHS[layer.icon]) {
          // Tabler outline icons live on a 24-unit grid, stroke 2; scale into the bbox.
          const k = width / 24;
          return (
            <G key={layer.layer_id} transform={`translate(${x}, ${y}) scale(${k})`}>
              {ICON_PATHS[layer.icon].map((d, i) => (
                <Path
                  key={i}
                  d={d}
                  fill="none"
                  stroke={layer.color?.hex ?? "#FFFFFF"}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ))}
            </G>
          );
        }
        if (layer.type === "shape" && layer.shape === "ellipse") {
          return (
            <Ellipse
              key={layer.layer_id}
              cx={x + width / 2}
              cy={y + height / 2}
              rx={width / 2}
              ry={height / 2}
              fill={layer.color?.hex ?? "#CCCCCC"}
              fillOpacity={layer.color?.opacity ?? 1}
            />
          );
        }
        if (layer.type === "shape") {
          return (
            <Rect
              key={layer.layer_id}
              x={x}
              y={y}
              width={width}
              height={height}
              fill={layer.color?.hex ?? "#CCCCCC"}
              fillOpacity={layer.color?.opacity ?? 1}
            />
          );
        }
        if (layer.type === "image" && layer.raster_url) {
          // layer.raster_url from the backend is a relative, unauthenticated path -
          // a hint for humans reading the JSON, not something a client can fetch.
          // rasterUrl() rebuilds the real address with the base URL and the agent
          // token as a query param, since react-native-svg's Image href can't carry
          // an Authorization header.
          return (
            <SvgImage
              key={layer.layer_id}
              href={{ uri: rasterUrl(jobId, layer.layer_id) }}
              x={x}
              y={y}
              width={width}
              height={height}
              preserveAspectRatio="xMidYMid slice"
            />
          );
        }
        if (layer.type === "image") {
          // No raster yet (render fell back, or still in progress): a soft placeholder
          // block in the plan's own colour rather than a blank gap.
          return (
            <Rect
              key={layer.layer_id}
              x={x}
              y={y}
              width={width}
              height={height}
              fill={layer.color?.hex ?? "#CCCCCC"}
              fillOpacity={layer.color?.opacity ?? 0.35}
            />
          );
        }
        if (layer.type === "text" && layer.text) {
          const size = layer.typography?.font_size ?? 24;
          const lineHeight = (layer.typography?.line_height ?? 1.15) * size;
          const anchor =
            layer.align === "center" ? "middle" : layer.align === "right" ? "end" : "start";
          const anchorX = layer.align === "center" ? x + width / 2 : layer.align === "right" ? x + width : x;
          // Same wrap estimate layout.py used to size the box, so lines land inside it.
          const lines = wrap(layer.text, Math.max(1, Math.floor(width / (size * 0.52))));
          const isButton = !!layer.background;
          const padX = isButton ? size * 0.9 : 0;
          return (
            <G key={layer.layer_id}>
              {isButton && (
                <Rect
                  x={x}
                  y={y}
                  width={width}
                  height={height}
                  rx={size * 0.25}
                  fill={layer.background!.hex}
                  fillOpacity={layer.background!.opacity}
                />
              )}
              <SvgText
                fontSize={size}
                fontWeight={layer.typography?.font_weight ?? 400}
                fontFamily={layer.typography?.font_family ?? "System"}
                letterSpacing={layer.typography?.letter_spacing ?? 0}
                fill={layer.color?.hex ?? "#111111"}
                textAnchor={isButton ? "start" : anchor}
              >
                {lines.map((line, i) => (
                  <TSpan
                    key={i}
                    x={isButton ? x + padX : anchorX}
                    y={y + (isButton ? (height - size) / 2 : 0) + size * 0.9 + i * lineHeight}
                  >
                    {line}
                  </TSpan>
                ))}
              </SvgText>
            </G>
          );
        }
        return null;
      })}
    </Svg>
  );
}
