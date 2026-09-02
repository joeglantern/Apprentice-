/** Explore - the home screen and the app's shop window.
 *
 * Borderless artwork in a masonry with the prompt sitting on the image itself
 * rather than in a caption strip: the work is the interface. */

import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Image, ScrollView, StyleSheet, TextInput, View } from "react-native";

import { Icon } from "@/components/ui/Icon";
import { JobArtwork } from "@/components/ui/JobArtwork";
import { PressScale } from "@/components/ui/press";
import { Body, Display, Mono } from "@/components/ui/type";
import { coverAspect } from "@/hooks/useJobCover";
import { useJobHistory } from "@/hooks/useJobHistory";
import { radii, type } from "@/lib/tokens";
import type { JobKind, JobSummary } from "@/lib/types";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

const EMPTY = require("../../assets/brand/empty-frame.png");

type Filter = "all" | JobKind;
const FILTERS: Filter[] = ["all", "poster", "image", "logo"];

export default function ExploreScreen() {
  const { c, exploreColumns, isDesktop } = useTheme();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const { data, isLoading, isError, error } = useJobHistory();
  const done = useMemo(() => (data ?? []).filter((j) => j.status === "done"), [data]);

  const counts = useMemo(() => {
    const out = { all: done.length, poster: 0, image: 0, logo: 0 } as Record<Filter, number>;
    for (const j of done) out[j.kind] += 1;
    return out;
  }, [done]);

  const visible = useMemo(() => {
    const byKind = filter === "all" ? done : done.filter((j) => j.kind === filter);
    const q = query.trim().toLowerCase();
    return q ? byKind.filter((j) => j.prompt.toLowerCase().includes(q)) : byKind;
  }, [done, filter, query]);

  // Greedy shortest-column packing. React Native has no CSS columns, and a plain
  // even grid would leave a ragged gap under every card that is shorter than its row.
  const columns = useMemo(() => {
    const cols: JobSummary[][] = Array.from({ length: exploreColumns }, () => []);
    const heights = new Array<number>(exploreColumns).fill(0);
    for (const job of visible) {
      const shortest = heights.indexOf(Math.min(...heights));
      cols[shortest].push(job);
      heights[shortest] += 1 / coverAspect(job.kind);
    }
    return cols;
  }, [visible, exploreColumns]);

  return (
    <ScrollView style={styles.fill} contentContainerStyle={[styles.page, { paddingHorizontal: isDesktop ? 32 : 20 }]}>
      {/* Stacked on phone: a 250px search pill beside a 40px title does not fit in
          390, and a flex row that cannot wrap widens the whole document. */}
      <View style={[styles.header, !isDesktop && styles.headerStacked]}>
        <Display size={isDesktop ? type.displayXL : 40}>explore</Display>
        <View style={[styles.search, { backgroundColor: c.sf }, !isDesktop && styles.searchWide]}>
          <Icon name="search" size={14} color={c.t1} opacity={0.5} />
          <TextInput
            style={[styles.searchInput, { color: c.t1 }]}
            placeholder="search generations"
            placeholderTextColor={c.t3}
            value={query}
            onChangeText={setQuery}
          />
        </View>
      </View>

      <View style={[styles.filters, { borderBottomColor: c.ln }]}>
        {FILTERS.map((f) => {
          const on = filter === f;
          return (
            <PressScale key={f} scale={0.97} onPress={() => setFilter(f)}>
              <View style={[styles.filterInner, on && { borderBottomColor: c.t1 }]}>
                <Body size={type.bodySM} weight={on ? "600" : "400"} color={on ? c.t1 : c.t3}>
                  {f}
                </Body>
                <Mono size={type.monoXS} color={c.t3}>
                  {String(counts[f])}
                </Mono>
              </View>
            </PressScale>
          );
        })}
      </View>

      {visible.length === 0 ? (
        <Empty loading={isLoading} failed={isError} reason={(error as Error | null)?.message} narrowed={done.length > 0} />
      ) : (
        <View style={styles.masonry}>
          {columns.map((col, i) => (
            <View key={i} style={styles.column}>
              {col.map((job) => (
                <Card key={job.job_id} job={job} />
              ))}
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function Card({ job }: { job: JobSummary }) {
  const { c } = useTheme();
  const router = useRouter();
  const { setActiveJobId } = useSession();

  return (
    <PressScale
      scale={0.985}
      onPress={() => {
        setActiveJobId(job.job_id);
        router.push("/canvas");
      }}
      accessibilityRole="link"
      accessibilityLabel={job.prompt}
      style={[styles.card, { backgroundColor: c.sf0, aspectRatio: coverAspect(job.kind) }]}
    >
      <JobArtwork jobId={job.job_id} kind={job.kind} fill style={StyleSheet.absoluteFill} />
      <Body size={12.5} weight="500" color="#FFFFFF" numberOfLines={1} style={styles.caption}>
        {job.prompt}
      </Body>
    </PressScale>
  );
}

/** "Nothing here" and "could not ask" look identical unless the screen says which.
 * A silent fetch failure reading as an empty studio is how you end up staring at a
 * working app wondering why nothing happens. */
function Empty({
  loading,
  failed,
  reason,
  narrowed,
}: {
  loading: boolean;
  failed: boolean;
  reason?: string;
  narrowed: boolean;
}) {
  const { c } = useTheme();

  if (failed) {
    return (
      <View style={styles.empty}>
        <Body size={type.bodyMD} color={c.error}>
          cannot reach the server
        </Body>
        <Mono size={11} color={c.t3} style={styles.emptyReason}>
          {reason ?? "no response"}
        </Mono>
        <Mono size={11} color={c.t3}>
          check the address under settings
        </Mono>
      </View>
    );
  }

  return (
    <View style={styles.empty}>
      {loading ? null : <Image source={EMPTY} style={styles.emptyGlyph} />}
      <Body size={type.bodyMD} color={c.t2}>
        {loading ? "loading" : narrowed ? "nothing matches that" : "nothing generated yet"}
      </Body>
      {!loading && !narrowed ? (
        <Mono size={11} color={c.t3}>
          start on create
        </Mono>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  page: { paddingTop: 44, paddingBottom: 96, maxWidth: 1440, width: "100%", alignSelf: "center" },
  header: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: 24,
    marginBottom: 14,
  },
  headerStacked: { flexDirection: "column", alignItems: "stretch", gap: 16 },
  search: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderRadius: radii.chip,
    paddingHorizontal: 16,
    height: 40,
    minWidth: 250,
  },
  searchWide: { minWidth: 0, width: "100%" },
  searchInput: { flex: 1, fontSize: type.bodySM, fontFamily: type.body.family, minWidth: 0 },
  filters: {
    flexDirection: "row",
    alignItems: "center",
    gap: 20,
    flexWrap: "wrap",
    marginBottom: 26,
    borderBottomWidth: 1,
  },
  filterInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 44,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
    marginBottom: -1,
  },
  masonry: { flexDirection: "row", gap: 14 },
  column: { flex: 1, gap: 16 },
  card: { borderRadius: radii.mediaLg, overflow: "hidden", justifyContent: "flex-end" },
  caption: {
    paddingHorizontal: 14,
    paddingBottom: 11,
    textShadowColor: "rgba(0,0,0,0.85)",
    textShadowRadius: 10,
    textShadowOffset: { width: 0, height: 1 },
  },
  empty: { paddingVertical: 80, alignItems: "center", gap: 8 },
  emptyReason: { textAlign: "center", paddingHorizontal: 24 },
  emptyGlyph: { width: 56, height: 56, opacity: 0.8, marginBottom: 4 },
});
