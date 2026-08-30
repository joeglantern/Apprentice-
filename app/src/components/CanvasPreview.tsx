import Svg, { Image as SvgImage, Rect, Text as SvgText } from "react-native-svg";

import { rasterUrl } from "@/lib/api";
import type { Layer } from "@/lib/types";

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
    <Svg width="100%" viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
      {ordered.map((layer) => {
        const { x, y, width, height } = layer.bbox;
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
          return (
            <SvgText
              key={layer.layer_id}
              x={x}
              y={y + size}
              fontSize={size}
              fontWeight={layer.typography?.font_weight ?? 400}
              fontFamily={layer.typography?.font_family ?? "System"}
              fill={layer.color?.hex ?? "#111111"}
              textAnchor={
                layer.align === "center" ? "middle" : layer.align === "right" ? "end" : "start"
              }
            >
              {layer.text}
            </SvgText>
          );
        }
        return null;
      })}
    </Svg>
  );
}
