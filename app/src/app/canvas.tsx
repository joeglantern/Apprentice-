import { useLocalSearchParams, useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CanvasPreview } from "@/components/CanvasPreview";
import { ProgressBar } from "@/components/ProgressBar";
import { useGenerationProgress } from "@/hooks/useGenerationProgress";
import { useJob } from "@/hooks/useJob";
import { reviseJob } from "@/lib/api";
import { useState } from "react";

const COMPOSITIONS = ["anchor", "centered", "split"] as const;
const TYPEFACES = ["inter", "bebas", "playfair", "grotesk"] as const;

export default function CanvasScreen() {
  const { jobId, prompt } = useLocalSearchParams<{ jobId: string; prompt?: string }>();
  const job = useJob(jobId ?? null);
  const live = useGenerationProgress(jobId ?? null);

  const router = useRouter();
  const [revising, setRevising] = useState(false);

  const revise = async (changes: Parameters<typeof reviseJob>[1]) => {
    if (!jobId || revising) return;
    setRevising(true);
    try {
      const accepted = await reviseJob(jobId, changes);
      router.replace({ pathname: "/canvas", params: { jobId: accepted.job_id, prompt } });
    } finally {
      setRevising(false);
    }
  };

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
              jobId={jobId ?? ""}
              layers={result.layers}
              canvasWidth={result.canvas_width}
              canvasHeight={result.canvas_height}
            />
          </View>
        )}

        {job.data?.kind === "poster" && status === "done" && (
          <View style={styles.revise}>
            <Text style={styles.reviseLabel}>Adjust</Text>
            <View style={styles.reviseRow}>
              {COMPOSITIONS.map((c) => (
                <Pressable
                  key={c}
                  disabled={revising}
                  onPress={() => revise({ composition: c })}
                  style={[styles.chip, plan?.composition === c && styles.chipOn]}
                >
                  <Text style={styles.chipText}>{c}</Text>
                </Pressable>
              ))}
            </View>
            <View style={styles.reviseRow}>
              {TYPEFACES.map((t) => (
                <Pressable
                  key={t}
                  disabled={revising}
                  onPress={() => revise({ typeface: t })}
                  style={[styles.chip, plan?.typeface === t && styles.chipOn]}
                >
                  <Text style={styles.chipText}>{t}</Text>
                </Pressable>
              ))}
            </View>
            <Pressable
              disabled={revising}
              onPress={() => revise({ rerender_photo: true })}
              style={styles.chip}
            >
              <Text style={styles.chipText}>New photo</Text>
            </Pressable>
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
  revise: { gap: 8 },
  reviseLabel: { color: "#6B707A", fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 },
  reviseRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#2A2D34",
    backgroundColor: "#15161B",
  },
  chipOn: { borderColor: "#F4F5F7" },
  chipText: { color: "#C7CAD1", fontSize: 13 },
  rationale: { gap: 6 },
  rationaleLabel: { color: "#6B707A", fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 },
  rationaleText: { color: "#C7CAD1", fontSize: 14, lineHeight: 20 },
});
