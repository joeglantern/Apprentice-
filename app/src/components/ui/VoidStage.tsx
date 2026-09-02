/** The textured void behind auth, onboarding and the create stage.
 *
 * The handoff ships this as texture-void.png, a grain vignette. That file is larger
 * than the design API will hand over in one piece, and it is procedural anyway - so
 * it is drawn here instead: a soft radial lift out of the void, with the app's own
 * grain (already over everything, from the root layout) supplying the tooth. Costs
 * no asset and stays sharp at any window size. */

import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Defs, RadialGradient, Rect, Stop } from "react-native-svg";

import { useTheme } from "@/theme/theme";

export function VoidStage({
  children,
  style,
}: {
  children?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const { c } = useTheme();

  return (
    <View style={[styles.fill, { backgroundColor: c.void }, style]}>
      {/* width/height are required: an Svg sized only by absoluteFill falls back to
          the SVG intrinsic default of 300x150 and paints a rectangle in the corner. */}
      <Svg width="100%" height="100%" style={StyleSheet.absoluteFill} pointerEvents="none">
        <Defs>
          {/* Centred slightly high, where the eye lands first. */}
          <RadialGradient id="voidLift" cx="50%" cy="42%" r="75%">
            <Stop offset="0%" stopColor={c.sf} stopOpacity={0.85} />
            <Stop offset="55%" stopColor={c.void} stopOpacity={0.45} />
            <Stop offset="100%" stopColor="#000000" stopOpacity={0.9} />
          </RadialGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#voidLift)" />
      </Svg>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});
