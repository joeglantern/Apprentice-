/** The 2.5% grain over the whole app.
 *
 * The prototype does it with an feTurbulence data-URI, which react-native-svg will
 * not render on native. The obvious port - an Image with resizeMode="repeat" - is
 * worse: react-native-web does not implement `repeat`, so on web it lays one 128px
 * tile in the corner and calls it done. An SVG pattern tiles on both. */

import { StyleSheet, View } from "react-native";
import Svg, { Defs, Image as SvgImage, Pattern, Rect } from "react-native-svg";

const GRAIN = require("../../../assets/brand/grain.png");
const TILE = 128;

export function Grain({ opacity = 0.025 }: { opacity?: number }) {
  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.layer]}>
      <Svg width="100%" height="100%" opacity={opacity}>
        <Defs>
          <Pattern id="grain" patternUnits="userSpaceOnUse" width={TILE} height={TILE}>
            <SvgImage href={GRAIN} x="0" y="0" width={TILE} height={TILE} preserveAspectRatio="none" />
          </Pattern>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#grain)" />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  // Above content, below anything that has to stay readable (toasts, decks).
  layer: { zIndex: 90 },
});
