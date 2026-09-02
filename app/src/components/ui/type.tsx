/** The type ramp. Three faces, each with one job:
 *  Display - Space Grotesk, lowercase screen titles, optical tracking.
 *  Body    - Inter, everything a person reads as prose or a control label.
 *  Mono    - JetBrains Mono, ids, seeds, sizes, and the small-caps section labels.
 *
 * Tracking in the design is quoted in em; React Native wants px, so it is applied
 * as a multiple of the size rather than a fixed number that would only be right
 * at one step of the ramp. */

import { Text, type StyleProp, type TextProps, type TextStyle } from "react-native";

import { type } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

type Weight = "400" | "500" | "600" | "700";

interface Base extends TextProps {
  size?: number;
  color?: string;
  weight?: Weight;
  style?: StyleProp<TextStyle>;
}

export function Display({ size = type.displayLG, color, weight = "600", style, ...rest }: Base) {
  const { c } = useTheme();
  return (
    <Text
      {...rest}
      style={[
        {
          fontFamily: type.display.family,
          fontSize: size,
          fontWeight: weight,
          color: color ?? c.t1,
          letterSpacing: size * type.display.tracking,
          lineHeight: size * 1.0,
        },
        style,
      ]}
    />
  );
}

export function Body({ size = type.bodyMD, color, weight = "400", style, ...rest }: Base) {
  const { c } = useTheme();
  return (
    <Text
      {...rest}
      style={[
        { fontFamily: type.body.family, fontSize: size, fontWeight: weight, color: color ?? c.t1 },
        style,
      ]}
    />
  );
}

export function Mono({ size = type.monoMD, color, weight = "400", style, ...rest }: Base) {
  const { c } = useTheme();
  return (
    <Text
      {...rest}
      style={[
        { fontFamily: type.mono.family, fontSize: size, fontWeight: weight, color: color ?? c.t2 },
        style,
      ]}
    />
  );
}

/** The uppercase section rubric that opens each block: SERVER, LAYERS, RUNNING. */
export function MonoLabel({ children, color, style, ...rest }: Base & { children: string }) {
  const { c } = useTheme();
  return (
    <Text
      {...rest}
      style={[
        {
          fontFamily: type.mono.family,
          fontSize: type.monoXS,
          letterSpacing: type.monoLabelTracking,
          color: color ?? c.t3,
        },
        style,
      ]}
    >
      {children.toUpperCase()}
    </Text>
  );
}
