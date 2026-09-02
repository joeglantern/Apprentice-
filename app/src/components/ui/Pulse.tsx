/** A slow opacity breath, used wherever the app is saying "this is live": the jobs
 * badge on the rail, the active stage dot on a job card, the Eidolon mark while the
 * model is working, the idle create stage. */

import { useEffect, useState } from "react";
import { Animated, Easing, type StyleProp, type ViewStyle } from "react-native";

import { motion } from "@/lib/tokens";

export function Pulse({
  style,
  durationMs = motion.pulseLoopMs,
  min = 0.4,
  children,
}: {
  style?: StyleProp<ViewStyle>;
  durationMs?: number;
  min?: number;
  children?: React.ReactNode;
}) {
  const [v] = useState(() => new Animated.Value(1));

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(v, {
          toValue: min,
          duration: durationMs / 2,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(v, {
          toValue: 1,
          duration: durationMs / 2,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [v, durationMs, min]);

  return <Animated.View style={[style, { opacity: v }]}>{children}</Animated.View>;
}
