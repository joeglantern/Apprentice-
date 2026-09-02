/** Press feedback for the whole app: a spring down to the design's press scale and
 * back. 0.97 for anything with a body, 0.92 for the small round buttons (generate,
 * send, rail items) where a subtler scale would not read.
 *
 * The Pressable itself is the animated element. Wrapping an inner Animated.View
 * instead would look identical in isolation and silently break layout: `flex: 1`,
 * `marginLeft: auto` and `alignSelf` would land on the inner view while the
 * Pressable stayed content-sized, so a row of tabs collapses instead of dividing
 * the bar.
 *
 * Hover is gated on a fine pointer: on a touch device react-native-web latches
 * hover after a tap and the control stays lit until you touch something else. */

import { useState } from "react";
import {
  Animated,
  Platform,
  Pressable,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { motion } from "@/lib/tokens";

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

interface Props extends Omit<PressableProps, "style"> {
  style?: StyleProp<ViewStyle>;
  /** 0.97 default; pass 0.92 for small round controls. */
  scale?: number;
  children: React.ReactNode;
}

export function PressScale({ style, scale = motion.press, children, ...rest }: Props) {
  // Lazy state, not a ref: an Animated.Value is created once and never reassigned,
  // and React 19 refuses ref reads during render.
  const [v] = useState(() => new Animated.Value(1));

  const to = (value: number) =>
    Animated.spring(v, {
      toValue: value,
      useNativeDriver: true,
      speed: 40,
      bounciness: 4,
    }).start();

  return (
    <AnimatedPressable
      {...rest}
      onPressIn={(e) => {
        to(scale);
        rest.onPressIn?.(e);
      }}
      onPressOut={(e) => {
        to(1);
        rest.onPressOut?.(e);
      }}
      style={[style, { transform: [{ scale: v }] }]}
    >
      {children}
    </AnimatedPressable>
  );
}

/** True only where a real cursor exists, so hover styling never latches on touch. */
export const hasFinePointer =
  Platform.OS === "web" &&
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(pointer: fine)").matches;
