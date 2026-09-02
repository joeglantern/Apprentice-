/** A finished piece, composed.
 *
 * A poster is not its background photograph - it is 30-odd layers of shape, type
 * and raster stacked in the plan's own coordinate system. CanvasPreview draws that
 * stack as SVG, which is what makes the result identical on web and on a phone and
 * keeps the type crisp at any size. Anywhere the app shows a finished job (explore
 * card, canvas detail, the create stage, a chat turn) it shows this, not a raster,
 * so the thing on screen is the design rather than one layer of it.
 *
 * Falls back to the cover raster while the job detail is still loading, so a grid
 * fills in progressively instead of staying blank. */

import { Image, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { CanvasPreview } from "@/components/CanvasPreview";
import { useJob } from "@/hooks/useJob";
import { coverAspect } from "@/hooks/useJobCover";
import { rasterUrl } from "@/lib/api";
import type { JobKind } from "@/lib/types";
import { useTheme } from "@/theme/theme";

interface Props {
  jobId: string;
  /** Reserves the right shape before the layers arrive. */
  kind?: JobKind;
  style?: StyleProp<ViewStyle>;
  /** Let the caller own the aspect (canvas detail sizes to the real canvas). */
  fill?: boolean;
}

export function JobArtwork({ jobId, kind = "poster", style, fill }: Props) {
  const { c } = useTheme();
  const { data } = useJob(jobId || null);
  const result = data?.result;

  const aspect = result ? result.canvas_width / result.canvas_height : coverAspect(kind);

  // Something to look at while the 30-layer detail is in flight.
  const firstRaster = result?.layers.find((l) => l.type === "image" && l.raster_key);

  return (
    <View
      style={[styles.wrap, { backgroundColor: c.sf0 }, fill ? null : { aspectRatio: aspect }, style]}
    >
      {result?.layers.length ? (
        <CanvasPreview
          jobId={jobId}
          layers={result.layers}
          canvasWidth={result.canvas_width}
          canvasHeight={result.canvas_height}
        />
      ) : firstRaster ? (
        <Image
          source={{ uri: rasterUrl(jobId, firstRaster.layer_id) }}
          resizeMode="cover"
          style={StyleSheet.absoluteFill}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { overflow: "hidden" },
});
