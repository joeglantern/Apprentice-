/** The list of sessions, presentational only.
 *
 * Text rows, no thumbnails. A cover per row would mean fetching each session's job,
 * and a job carries its whole plan and layer stack: thirty heavy requests to paint a
 * sidebar. If covers are wanted later the answer is a cover field on the summary,
 * not a fetch per row. */

import { ScrollView, StyleSheet, View } from "react-native";

import { Icon } from "@/components/ui/Icon";
import { PressScale, hasFinePointer } from "@/components/ui/press";
import { Body, Mono, MonoLabel } from "@/components/ui/type";
import { useDeleteThread } from "@/hooks/useDeleteThread";
import { useThreads } from "@/hooks/useThreads";
import { relative } from "@/lib/time";
import { radii, type } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

export function SessionList({
  activeId,
  onOpen,
  onNew,
}: {
  activeId: string | null;
  onOpen: (threadId: string) => void;
  onNew: () => void;
}) {
  const { c } = useTheme();
  const { data, isLoading } = useThreads();
  const remove = useDeleteThread();
  const sessions = data ?? [];

  return (
    <View style={styles.root}>
      <View style={styles.head}>
        <MonoLabel>sessions</MonoLabel>
        <PressScale
          scale={0.9}
          onPress={onNew}
          accessibilityRole="button"
          accessibilityLabel="new session"
          style={styles.new}
        >
          <Icon name="plusSquare" size={15} color={c.t2} />
        </PressScale>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.rows}>
        {sessions.length === 0 ? (
          <Mono size={type.monoXS} color={c.t4} style={styles.empty}>
            {isLoading ? "loading" : "nothing yet"}
          </Mono>
        ) : null}

        {sessions.map((s) => {
          const on = s.thread_id === activeId;
          return (
            <PressScale
              key={s.thread_id}
              scale={0.99}
              onPress={() => onOpen(s.thread_id)}
              accessibilityRole="link"
              accessibilityLabel={s.title}
              accessibilityState={{ selected: on }}
              style={[styles.row, on && { backgroundColor: c.raise }]}
            >
              <View style={styles.rowText}>
                <Body size={type.bodyXS} color={on ? c.t1 : c.t2} numberOfLines={1}>
                  {s.title}
                </Body>
                <Mono size={9} color={c.t4}>
                  {relative(s.updated_at)}
                </Mono>
              </View>
              {hasFinePointer ? (
                <PressScale
                  scale={0.9}
                  onPress={() => remove.mutate(s.thread_id)}
                  accessibilityRole="button"
                  accessibilityLabel={`forget ${s.title}`}
                  style={styles.forget}
                >
                  <Icon name="trash" size={13} color={c.t3} />
                </PressScale>
              ) : null}
            </PressScale>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, minHeight: 0, width: "100%" },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 6, marginBottom: 6 },
  new: { width: 26, height: 26, alignItems: "center", justifyContent: "center", borderRadius: 8 },
  scroll: { flex: 1 },
  rows: { gap: 2, paddingBottom: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 7,
    borderRadius: radii.thumb,
  },
  rowText: { flex: 1, minWidth: 0, gap: 1 },
  forget: { width: 22, height: 22, alignItems: "center", justifyContent: "center" },
  empty: { paddingHorizontal: 8, paddingVertical: 6 },
});
