/** Arrival. A render, a message, a phase of the create stage: anything that appears
 * because something finished fades up rather than snapping in.
 *
 * This is the design system's `motion.fadeUpMs`, which has been declared since the
 * tokens were written and until now had nothing using it. Native driver, fired once
 * on mount, so it costs a frame and never runs again. */

import { useEffect, useState } from "react";
import { Animated, Easing, type StyleProp, type ViewStyle } from "react-native";

import { motion } from "@/lib/tokens";

export function Enter({
  children,
  style,
  delayMs = 0,
  /** For the pieces of a list that were already there when it opened: they should
   * simply be present, not all animate at once. */
  disabled = false,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  delayMs?: number;
  disabled?: boolean;
}) {
  const [v] = useState(() => new Animated.Value(disabled ? 1 : 0));

  useEffect(() => {
    if (disabled) return;
    const anim = Animated.timing(v, {
      toValue: 1,
      duration: motion.fadeUpMs,
      delay: delayMs,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    });
    anim.start();
    return () => anim.stop();
  }, [v, delayMs, disabled]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity: v,
          transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}
