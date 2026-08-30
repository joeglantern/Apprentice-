import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AestheticSelector } from "@/components/AestheticSelector";
import { PromptInput } from "@/components/PromptInput";
import { useAesthetics } from "@/hooks/useAesthetics";
import { useGenerate } from "@/hooks/useGenerate";
import type { BrandKit, JobKind } from "@/lib/types";

const BASELINE = "baseline";
const KINDS: { value: JobKind; label: string }[] = [
  { value: "poster", label: "Poster" },
  { value: "image", label: "Photo" },
  { value: "logo", label: "Logo" },
];

export default function PromptScreen() {
  const router = useRouter();
  const aesthetics = useAesthetics();
  const generate = useGenerate();
  const [aestheticVersion, setAestheticVersion] = useState(BASELINE);
  const [kind, setKind] = useState<JobKind>("poster");
  const [brandOpen, setBrandOpen] = useState(false);
  const [brandName, setBrandName] = useState("");
  const [brandPalette, setBrandPalette] = useState("");

  // "#1A2B3C, #F2A623" -> ["#1A2B3C", "#F2A623"]; junk entries are just dropped.
  const brand = (): BrandKit | undefined => {
    if (!brandName.trim()) return undefined;
    const palette = brandPalette
      .split(/[,\s]+/)
      .map((c) => c.trim().toUpperCase())
      .filter((c) => /^#[0-9A-F]{6}$/.test(c));
    return { name: brandName.trim(), palette };
  };

  const onSubmit = (prompt: string) => {
    generate.mutate(
      { prompt, aestheticVersion, kind, brand: brand() },
      {
        onSuccess: (accepted) => {
          router.push({ pathname: "/canvas", params: { jobId: accepted.job_id, prompt } });
        },
      },
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <View style={styles.headerRow}>
            <Text style={styles.title}>Ghost Agent</Text>
            <Pressable onPress={() => router.push("/history")}>
              <Text style={styles.historyLink}>History</Text>
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Describe the piece. The director plans it, the renderer paints it, in the
            designer&apos;s signature style once one exists.
          </Text>
        </View>

        <View style={styles.kinds}>
          {KINDS.map((k) => (
            <Pressable
              key={k.value}
              onPress={() => setKind(k.value)}
              style={[styles.kind, kind === k.value && styles.kindOn]}
            >
              <Text style={[styles.kindText, kind === k.value && styles.kindTextOn]}>{k.label}</Text>
            </Pressable>
          ))}
        </View>

        <AestheticSelector
          aesthetics={aesthetics.data ?? []}
          selected={aestheticVersion}
          onSelect={setAestheticVersion}
        />

        <Pressable onPress={() => setBrandOpen(!brandOpen)}>
          <Text style={styles.brandToggle}>
            {brandOpen ? "Hide brand kit" : "Brand kit (optional)"}
          </Text>
        </Pressable>
        {brandOpen && (
          <View style={styles.brandBox}>
            <TextInput
              style={styles.brandInput}
              placeholder="Brand name"
              placeholderTextColor="#6B707A"
              value={brandName}
              onChangeText={setBrandName}
            />
            <TextInput
              style={styles.brandInput}
              placeholder="Palette, e.g. #1A2B3C #F2A623"
              placeholderTextColor="#6B707A"
              autoCapitalize="characters"
              value={brandPalette}
              onChangeText={setBrandPalette}
            />
          </View>
        )}

        <PromptInput onSubmit={onSubmit} busy={generate.isPending} />

        {generate.isError && (
          <Text style={styles.error}>{(generate.error as Error).message}</Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0B0B0F" },
  container: { padding: 20, gap: 20 },
  header: { gap: 8 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { color: "#F4F5F7", fontSize: 28, fontWeight: "700" },
  historyLink: { color: "#8A8F98", fontSize: 14 },
  subtitle: { color: "#8A8F98", fontSize: 14, lineHeight: 20 },
  error: { color: "#E5484D", fontSize: 13 },
  kinds: { flexDirection: "row", gap: 8 },
  kind: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#2A2D34",
    backgroundColor: "#15161B",
  },
  kindOn: { backgroundColor: "#F4F5F7", borderColor: "#F4F5F7" },
  kindText: { color: "#C7CAD1", fontSize: 13 },
  kindTextOn: { color: "#0B0B0F", fontWeight: "600" },
  brandToggle: { color: "#8A8F98", fontSize: 13 },
  brandBox: { gap: 8 },
  brandInput: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#2A2D34",
    backgroundColor: "#15161B",
    color: "#F4F5F7",
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
});
