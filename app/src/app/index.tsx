import { useRouter } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AestheticSelector } from "@/components/AestheticSelector";
import { PromptInput } from "@/components/PromptInput";
import { useAesthetics } from "@/hooks/useAesthetics";
import { useGenerate } from "@/hooks/useGenerate";

const BASELINE = "baseline";

export default function PromptScreen() {
  const router = useRouter();
  const aesthetics = useAesthetics();
  const generate = useGenerate();
  const [aestheticVersion, setAestheticVersion] = useState(BASELINE);

  const onSubmit = (prompt: string) => {
    generate.mutate(
      { prompt, aestheticVersion },
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
          <Text style={styles.title}>Ghost Agent</Text>
          <Text style={styles.subtitle}>
            Describe the piece. The director plans it, the renderer paints it, in the
            designer&apos;s signature style once one exists.
          </Text>
        </View>

        <AestheticSelector
          aesthetics={aesthetics.data ?? []}
          selected={aestheticVersion}
          onSelect={setAestheticVersion}
        />

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
  title: { color: "#F4F5F7", fontSize: 28, fontWeight: "700" },
  subtitle: { color: "#8A8F98", fontSize: 14, lineHeight: 20 },
  error: { color: "#E5484D", fontSize: 13 },
});
