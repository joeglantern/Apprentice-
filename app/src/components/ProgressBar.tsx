import { StyleSheet, Text, View } from "react-native";

import type { JobStatus } from "@/lib/types";

const STAGES: JobStatus[] = ["queued", "planning", "layout", "render", "done"];
const LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  planning: "Thinking about the brief",
  layout: "Composing the layout",
  render: "Rendering",
  done: "Done",
  error: "Something went wrong",
};

interface Props {
  status: JobStatus;
  message?: string;
}

export function ProgressBar({ status, message }: Props) {
  if (status === "error") {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>{message ?? "Generation failed"}</Text>
      </View>
    );
  }

  const activeIndex = Math.max(0, STAGES.indexOf(status));

  return (
    <View style={styles.container}>
      <View style={styles.track}>
        {STAGES.map((stage, i) => (
          <View
            key={stage}
            style={[styles.segment, i <= activeIndex && styles.segmentActive]}
          />
        ))}
      </View>
      <Text style={styles.label}>{message ?? LABELS[status]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  track: { flexDirection: "row", gap: 4, height: 6 },
  segment: { flex: 1, borderRadius: 3, backgroundColor: "#2A2D34" },
  segmentActive: { backgroundColor: "#F4F5F7" },
  label: { color: "#8A8F98", fontSize: 13 },
  errorText: { color: "#E5484D", fontSize: 13 },
});
