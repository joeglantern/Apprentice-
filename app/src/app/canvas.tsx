import { useLocalSearchParams } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CanvasPreview } from "@/components/CanvasPreview";
import { ProgressBar } from "@/components/ProgressBar";
import { useGenerationProgress } from "@/hooks/useGenerationProgress";
import { useJob } from "@/hooks/useJob";

export default function CanvasScreen() {
  const { jobId, prompt } = useLocalSearchParams<{ jobId: string; prompt?: string }>();
  const job = useJob(jobId ?? null);
  const live = useGenerationProgress(jobId ?? null);

  const status = live?.stage ?? job.data?.status ?? "queued";
  const isTerminal = status === "done" || status === "error";
  const result = job.data?.result;
  const plan = job.data?.plan;

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        {!!prompt && <Text style={styles.prompt}>{prompt}</Text>}

        {!isTerminal && <ProgressBar status={status} message={live?.message} />}

        {status === "error" && (
          <Text style={styles.error}>{job.data?.error ?? "Generation failed"}</Text>
        )}

        {result && (
          <View style={styles.canvasWrap}>
            <CanvasPreview
              layers={result.layers}
              canvasWidth={result.canvas_width}
              canvasHeight={result.canvas_height}
            />
          </View>
        )}

        {plan && (
          <View style={styles.rationale}>
            <Text style={styles.rationaleLabel}>Why this design</Text>
            <Text style={styles.rationaleText}>{plan.rationale}</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0B0B0F" },
  container: { padding: 20, gap: 20 },
  prompt: { color: "#8A8F98", fontSize: 14, fontStyle: "italic" },
  error: { color: "#E5484D", fontSize: 14 },
  canvasWrap: {
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#15161B",
    borderWidth: 1,
    borderColor: "#2A2D34",
  },
  rationale: { gap: 6 },
  rationaleLabel: { color: "#6B707A", fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 },
  rationaleText: { color: "#C7CAD1", fontSize: 14, lineHeight: 20 },
});
