/** Jobs - what the studio is doing right now, what is waiting, and what it did.
 *
 * A running job is shown the same way create shows it: the piece resolving out of
 * noise, with the backend's own stage line. Three sections so the eye can go
 * straight to the one it cares about. */

import { useRouter } from "expo-router";
import { useMemo } from "react";
import { Image, ScrollView, StyleSheet, View } from "react-native";

import { DenoisingPreview } from "@/components/ui/DenoisingPreview";
import { Icon } from "@/components/ui/Icon";
import { Pill } from "@/components/ui/controls";
import { PressScale } from "@/components/ui/press";
import { Pulse } from "@/components/ui/Pulse";
import { Body, Display, Mono, MonoLabel } from "@/components/ui/type";
import { useGenerationProgress } from "@/hooks/useGenerationProgress";
import { useJob } from "@/hooks/useJob";
import { useJobCover } from "@/hooks/useJobCover";
import { useJobHistory } from "@/hooks/useJobHistory";
import { readProgress } from "@/lib/progress";
import { calendar, relative } from "@/lib/time";
import { radii, type } from "@/lib/tokens";
import type { JobStatus, JobSummary } from "@/lib/types";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

const EMPTY = require("../../assets/brand/empty-queue.png");

const RUNNING: JobStatus[] = ["planning", "layout", "render"];

/** The pipeline a person actually cares about, and which backend stage lights it. */
const PIPELINE: { label: string; stage: JobStatus }[] = [
  { label: "plan", stage: "planning" },
  { label: "compose", stage: "layout" },
  { label: "render", stage: "render" },
];

export default function JobsScreen() {
  const { c, isDesktop } = useTheme();
  const { data } = useJobHistory();

  const { running, queued, history } = useMemo(() => {
    const all = data ?? [];
    return {
      running: all.filter((j) => RUNNING.includes(j.status)),
      queued: all.filter((j) => j.status === "queued"),
      history: all.filter((j) => j.status === "done" || j.status === "error"),
    };
  }, [data]);

  const empty = !data?.length;

  return (
    <ScrollView contentContainerStyle={[styles.page, { paddingHorizontal: isDesktop ? 32 : 20 }]}>
      <View style={styles.header}>
        <Display size={isDesktop ? type.displayLG : 36}>jobs</Display>
        <Mono size={10} color={c.t3} style={styles.summary}>
          {running.length} running · {queued.length} queued · {history.length} done
        </Mono>
      </View>

      {empty ? (
        <View style={styles.empty}>
          <Image source={EMPTY} style={styles.emptyGlyph} />
          <Body size={type.bodyMD} color={c.t2}>
            nothing in the queue
          </Body>
        </View>
      ) : null}

      {running.length ? (
        <View style={styles.section}>
          <MonoLabel>running</MonoLabel>
          {running.map((j) => (
            <RunningCard key={j.job_id} job={j} />
          ))}
        </View>
      ) : null}

      {queued.length ? (
        <View style={styles.section}>
          <MonoLabel>queued</MonoLabel>
          {queued.map((j, i) => (
            <View key={j.job_id} style={[styles.queuedRow, { backgroundColor: c.sf0 }]}>
              <Mono size={10} color={c.t4}>
                {shortId(j.job_id)}
              </Mono>
              <Body size={type.bodySM} color={c.t2} numberOfLines={1} style={styles.grow}>
                {j.prompt}
              </Body>
              <View style={[styles.posPill, { backgroundColor: c.raise }]}>
                <Mono size={type.monoXS} color={c.t3}>
                  {i === 0 ? "next up" : `#${i + 1}`}
                </Mono>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {history.length ? (
        <View style={styles.historySection}>
          <MonoLabel style={styles.historyLabel}>history</MonoLabel>
          {history.map((j) => (
            <HistoryRow key={j.job_id} job={j} />
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function RunningCard({ job }: { job: JobSummary }) {
  const { c } = useTheme();
  const { data: full } = useJob(job.job_id);
  const event = useGenerationProgress(job.job_id);
  const progress = readProgress(full, event);
  const cover = useJobCover(job.job_id);

  const reached = PIPELINE.findIndex((p) => p.stage === progress.status);

  return (
    <View style={[styles.card, { backgroundColor: c.sf }]}>
      <DenoisingPreview
        source={cover ? { uri: cover } : undefined}
        pct={progress.pct}
        radius={11}
        style={styles.thumb}
      />
      <View style={styles.cardBody}>
        <View style={styles.cardTop}>
          <Mono size={10} color={c.t4}>
            {shortId(job.job_id)}
          </Mono>
          <Body size={11} color={c.t4} style={styles.tabular}>
            {relative(job.created_at)}
          </Body>
        </View>

        <Body size={type.bodyMD} numberOfLines={1}>
          {job.prompt}
        </Body>

        <View style={styles.stages}>
          {PIPELINE.map((p, i) => {
            const done = reached > i;
            const active = reached === i;
            const dot = done ? c.success : active ? c.accent : c.ln2;
            const label = done ? c.t3 : active ? c.t1 : c.t4;
            return (
              <View key={p.label} style={styles.stage}>
                {active ? (
                  <Pulse style={[styles.stageDot, { backgroundColor: dot }]} />
                ) : (
                  <View style={[styles.stageDot, { backgroundColor: dot }]} />
                )}
                <Mono size={type.monoXS} color={label}>
                  {p.label}
                </Mono>
              </View>
            );
          })}
          <Body size={11.5} color={c.t2} numberOfLines={1} style={styles.stageMsg}>
            {progress.message}
          </Body>
        </View>

        <View style={[styles.bar, { backgroundColor: c.ln }]}>
          <View style={[styles.barFill, { backgroundColor: c.accent, width: `${progress.pct}%` }]} />
        </View>
      </View>
    </View>
  );
}

function HistoryRow({ job }: { job: JobSummary }) {
  const { c } = useTheme();
  const router = useRouter();
  const { setActiveJobId } = useSession();
  const failed = job.status === "error";
  const cover = useJobCover(failed ? "" : job.job_id);

  return (
    <PressScale
      scale={0.99}
      disabled={failed}
      onPress={() => {
        setActiveJobId(job.job_id);
        router.push("/canvas");
      }}
      style={[styles.historyRow, { borderBottomColor: c.ln }]}
    >
      <View style={[styles.historyThumb, { backgroundColor: c.sf, opacity: failed ? 0.5 : 1 }]}>
        {failed ? (
          <Icon name="alert" size={16} color={c.error} />
        ) : cover ? (
          <Image source={{ uri: cover }} resizeMode="cover" style={styles.fill} />
        ) : null}
      </View>

      <View style={styles.grow}>
        <Body size={type.bodySM} numberOfLines={1}>
          {job.prompt}
        </Body>
        <View style={styles.statusLine}>
          <View style={[styles.statusDot, { backgroundColor: failed ? c.error : c.success }]} />
          <Body size={11} color={c.t3} numberOfLines={1}>
            {failed ? "failed" : "done"}
          </Body>
        </View>
      </View>

      <Body size={11} color={c.t4} style={styles.tabular}>
        {calendar(job.created_at)}
      </Body>

      {failed ? <Pill label="retry" height={30} /> : null}
    </PressScale>
  );
}

/** Job ids are uuids; the design shows a short handle, which is all anyone quotes. */
function shortId(id: string): string {
  return `jb-${id.replace(/-/g, "").slice(0, 4)}`;
}

const styles = StyleSheet.create({
  page: { paddingTop: 44, paddingBottom: 96, maxWidth: 820, width: "100%", alignSelf: "center", gap: 26 },
  header: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" },
  summary: { paddingBottom: 6 },
  section: { gap: 10 },
  historySection: { gap: 4 },
  historyLabel: { paddingBottom: 6 },
  fill: { width: "100%", height: "100%" },
  grow: { flex: 1, minWidth: 0 },
  tabular: { fontVariant: ["tabular-nums"] },

  card: { flexDirection: "row", gap: 14, backgroundColor: "transparent", borderRadius: radii.mediaLg, padding: 14 },
  thumb: { width: 86, height: 86, flexShrink: 0 },
  cardBody: { flex: 1, minWidth: 0, gap: 7, justifyContent: "center" },
  cardTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  stages: { flexDirection: "row", alignItems: "center", gap: 16 },
  stage: { flexDirection: "row", alignItems: "center", gap: 6 },
  stageDot: { width: 6, height: 6, borderRadius: 3 },
  stageMsg: { marginLeft: "auto", flexShrink: 1 },
  bar: { height: 2, borderRadius: 1, overflow: "hidden" },
  barFill: { height: 2 },

  queuedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: radii.media,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  posPill: { borderRadius: radii.chip, paddingHorizontal: 9, paddingVertical: 3 },

  historyRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingVertical: 10,
    paddingHorizontal: 2,
    borderBottomWidth: 1,
  },
  historyThumb: {
    width: 42,
    height: 42,
    borderRadius: radii.thumb,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  statusLine: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 3 },
  statusDot: { width: 5, height: 5, borderRadius: 2.5 },

  empty: { paddingVertical: 60, alignItems: "center", gap: 10 },
  emptyGlyph: { width: 56, height: 56, opacity: 0.8 },
});
