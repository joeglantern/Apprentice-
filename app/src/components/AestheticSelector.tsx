import { FlatList, Pressable, StyleSheet, Text } from "react-native";

import type { Aesthetic } from "@/lib/types";

interface Props {
  aesthetics: Aesthetic[];
  selected: string;
  onSelect: (version: string) => void;
}

export function AestheticSelector({ aesthetics, selected, onSelect }: Props) {
  if (aesthetics.length <= 1) return null; // nothing to choose between yet

  return (
    <FlatList
      horizontal
      data={aesthetics}
      keyExtractor={(item) => item.version}
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.list}
      renderItem={({ item }) => {
        const active = item.version === selected;
        return (
          <Pressable
            style={[styles.chip, active && styles.chipActive]}
            onPress={() => onSelect(item.version)}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{item.label}</Text>
            {typeof item.trained_on === "number" && (
              <Text style={styles.meta}>{item.trained_on} images</Text>
            )}
          </Pressable>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  list: { gap: 8, paddingVertical: 4 },
  chip: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#2A2D34",
    backgroundColor: "#15161B",
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  chipActive: { borderColor: "#F4F5F7", backgroundColor: "#1D1F26" },
  label: { color: "#C7CAD1", fontSize: 13, fontWeight: "500" },
  labelActive: { color: "#F4F5F7" },
  meta: { color: "#6B707A", fontSize: 11, marginTop: 2 },
});
