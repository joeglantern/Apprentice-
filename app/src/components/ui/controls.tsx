/** The small controls the prompt deck, canvas panel and jobs list are built from.
 * They exist as one set so a chip in the create deck and a chip in the canvas
 * panel are the same object, not two things that happen to look alike. */

import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { radii, type } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

import { Body, Mono } from "./type";
import { PressScale } from "./press";

/** A run of mutually exclusive options in a sunken track: kind, size. The selected
 * one inverts to the text colour, which is the only place a light fill appears. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  mono = false,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  mono?: boolean;
}) {
  const { c } = useTheme();
  const Label = mono ? Mono : Body;
  return (
    <View style={[styles.track, { backgroundColor: c.sf0 }]}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <PressScale
            key={o.value}
            scale={0.96}
            onPress={() => onChange(o.value)}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            style={[styles.seg, mono && styles.segMono, on && { backgroundColor: c.t1 }]}
          >
            <Label
              size={mono ? 11 : type.bodyXS}
              weight={mono ? "400" : "500"}
              color={on ? c.bg0 : c.t2}
            >
              {o.label}
            </Label>
          </PressScale>
        );
      })}
    </View>
  );
}

/** An outlined chip that can carry a leading element (a kit's swatches, an
 * aesthetic's thumbnail). Selection is a border, not a fill. */
export function OutlineChip({
  label,
  selected,
  onPress,
  leading,
  style,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  leading?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const { c } = useTheme();
  return (
    <PressScale
      scale={0.96}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={[styles.outline, { borderColor: selected ? c.t1 : c.ln2 }, style]}
    >
      {leading}
      <Mono size={type.monoSM} color={selected ? c.t1 : c.t2} numberOfLines={1}>
        {label}
      </Mono>
    </PressScale>
  );
}

/** The raised action pill: remix, retry, open in canvas. */
export function Pill({
  label,
  onPress,
  tone = "raised",
  height = 38,
  style,
}: {
  label: string;
  onPress?: () => void;
  tone?: "raised" | "accent";
  height?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { c } = useTheme();
  const accent = tone === "accent";
  return (
    <PressScale
      onPress={onPress}
      accessibilityRole="button"
      style={[
        styles.pill,
        { height, backgroundColor: accent ? c.accent : c.raise, borderRadius: radii.chip },
        style,
      ]}
    >
      <Body size={type.bodySM} weight={accent ? "600" : "400"} color={accent ? c.bg0 : c.t1}>
        {label}
      </Body>
    </PressScale>
  );
}

/** A quiet suggestion in a chat turn or composer. */
export function QuickChip({ label, onPress, sunken = false }: { label: string; onPress: () => void; sunken?: boolean }) {
  const { c } = useTheme();
  return (
    <PressScale
      scale={0.96}
      onPress={onPress}
      accessibilityRole="button"
      style={[styles.quick, { backgroundColor: sunken ? c.sf0 : c.sf }]}
    >
      <Body size={sunken ? 11 : 11.5} color={c.t2}>
        {label}
      </Body>
    </PressScale>
  );
}

const styles = StyleSheet.create({
  track: { flexDirection: "row", borderRadius: radii.chip, padding: 3 },
  seg: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: radii.chip },
  segMono: { paddingHorizontal: 10 },
  outline: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    borderWidth: 1,
    borderRadius: radii.chip,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  pill: { alignItems: "center", justifyContent: "center", paddingHorizontal: 16 },
  quick: { borderRadius: radii.chip, paddingHorizontal: 11, paddingVertical: 4 },
});
