/** The one way this app shows work in progress.
 *
 * Never a spinner and never a bare bar: the piece being made is shown from the
 * first moment, heavily blurred, and resolves as the job advances. It is honest
 * feedback (you are looking at the actual render target) and it is the app's
 * signature moment, so it appears identically on the create stage, in a chat
 * turn, and on a jobs card - only the size changes.
 *
 * The prototype does the blur with a CSS filter, which exists on web only; here it
 * is expo-blur so native gets the same behaviour. Blur tracks the design's
 * (100 - pct) * 0.42 curve. */

import { useEffect, useState } from "react";
import { Animated, Easing, Image, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { BlurView } from "expo-blur";
import Svg, { Defs, RadialGradient, Rect, Stop } from "react-native-svg";

import { motion } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

interface Props {
  /** The render target. While the backend has nothing yet, pass undefined and the
   * field alone carries the moment. */
  source?: { uri: string } | number;
  /** 0-100. */
  pct: number;
  style?: StyleProp<ViewStyle>;
  /** Thin accent rule under the frame, as used on jobs cards. */
  showBar?: boolean;
  radius?: number;
}

export function DenoisingPreview({ source, pct, style, showBar = false, radius = 14 }: Props) {
  const { c } = useTheme();
  const [sweep] = useState(() => new Animated.Value(0));

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(sweep, {
        toValue: 1,
        duration: motion.scanLoopMs,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [sweep]);

  const clamped = Math.max(0, Math.min(100, pct));
  // expo-blur takes 0-100 intensity rather than a pixel radius; the design's
  // (100 - pct) * 0.42 px maps onto it proportionally over the same range.
  const intensity = Math.round(((100 - clamped) * 0.42 * 100) / 42);

  return (
    <View style={[styles.wrap, { borderRadius: radius, backgroundColor: c.sf0 }, style]}>
      {source ? <Image source={source} resizeMode="cover" style={StyleSheet.absoluteFill} /> : null}

      {intensity > 0 ? (
        <BlurView intensity={intensity} tint="dark" style={StyleSheet.absoluteFill} />
      ) : null}

      {/* Pulls the eye to the centre and keeps the edge in the void. */}
      <Svg width="100%" height="100%" style={StyleSheet.absoluteFill}>
        <Defs>
          <RadialGradient id="vig" cx="50%" cy="50%" r="72%">
            <Stop offset="40%" stopColor={c.void} stopOpacity={0} />
            <Stop offset="100%" stopColor={c.void} stopOpacity={1} />
          </RadialGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#vig)" />
      </Svg>

      <Animated.View
        pointerEvents="none"
        style={[
          styles.band,
          {
            backgroundColor: c.accent,
            transform: [
              {
                translateY: sweep.interpolate({ inputRange: [0, 1], outputRange: ["-120%", "1000%"] }),
              },
            ],
          },
        ]}
      />

      {showBar ? (
        <View style={[styles.barTrack, { backgroundColor: c.ln }]}>
          <View style={[styles.barFill, { backgroundColor: c.accent, width: `${clamped}%` }]} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { overflow: "hidden", position: "relative" },
  band: { position: "absolute", left: 0, right: 0, top: 0, height: 26, opacity: 0.32 },
  barTrack: { position: "absolute", left: 0, right: 0, bottom: 0, height: 2 },
  barFill: { height: 2 },
});
