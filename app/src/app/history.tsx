import { useRouter } from "expo-router";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useJobHistory } from "@/hooks/useJobHistory";
import type { JobSummary } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  planning: "Planning",
  layout: "Composing",
  render: "Rendering",
  done: "Done",
  error: "Failed",
};

export default function HistoryScreen() {
  const router = useRouter();
  const history = useJobHistory();

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <FlatList
        data={history.data ?? []}
        keyExtractor={(job) => job.job_id}
        contentContainerStyle={styles.list}
        onRefresh={() => history.refetch()}
        refreshing={history.isFetching}
        ListEmptyComponent={
          history.isError ? (
            <Text style={styles.error}>
              Couldn&apos;t load your history: {(history.error as Error).message}
            </Text>
          ) : !history.isLoading ? (
            <Text style={styles.empty}>No generations yet - try one from the prompt screen.</Text>
          ) : null
        }
        renderItem={({ item }: { item: JobSummary }) => (
          <Pressable
            style={styles.row}
            onPress={() =>
              router.push({
                pathname: "/canvas",
                params: { jobId: item.job_id, prompt: item.prompt },
              })
            }
          >
            <Text style={styles.prompt} numberOfLines={2}>
              {item.prompt}
            </Text>
            <View style={styles.meta}>
              <Text style={styles.status}>{STATUS_LABEL[item.status] ?? item.status}</Text>
              <Text style={styles.date}>
                {new Date(item.created_at).toLocaleString()}
              </Text>
            </View>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0B0B0F" },
  list: { padding: 16, gap: 10 },
  empty: { color: "#6B707A", fontSize: 14, textAlign: "center", marginTop: 40 },
  error: { color: "#E5484D", fontSize: 14, textAlign: "center", marginTop: 40 },
  row: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#2A2D34",
    backgroundColor: "#15161B",
    padding: 14,
    gap: 6,
  },
  prompt: { color: "#F4F5F7", fontSize: 15 },
  meta: { flexDirection: "row", justifyContent: "space-between" },
  status: { color: "#8A8F98", fontSize: 12 },
  date: { color: "#6B707A", fontSize: 12 },
});
