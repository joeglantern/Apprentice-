/** Brand kits - a client's fixed identity, which the director treats as binding
 * across a campaign. Picking one here attaches it and drops you straight into
 * create, because that is the only reason you came to this screen. */

import { useRouter } from "expo-router";
import { useMemo } from "react";
import { Image, ScrollView, StyleSheet, View, useWindowDimensions } from "react-native";

import { Icon } from "@/components/ui/Icon";
import { Pill } from "@/components/ui/controls";
import { PressScale } from "@/components/ui/press";
import { Body, Display, Mono } from "@/components/ui/type";
import { useJobCover } from "@/hooks/useJobCover";
import { useJobHistory } from "@/hooks/useJobHistory";
import { KITS, type Kit } from "@/lib/kits";
import { radii, type } from "@/lib/tokens";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

const MIN_CARD = 250;

export default function KitsScreen() {
  const { isDesktop } = useTheme();
  const { width } = useWindowDimensions();

  const pad = isDesktop ? 32 : 20;
  const rail = isDesktop ? 68 : 0;
  const available = Math.min(width - rail, 1100) - pad * 2;
  const columns = Math.max(1, Math.floor((available + 14) / (MIN_CARD + 14)));

  return (
    <ScrollView contentContainerStyle={[styles.page, { paddingHorizontal: pad }]}>
      <Display size={isDesktop ? type.displayLG : 36}>brand kits</Display>

      <View style={styles.grid}>
        {KITS.map((kit) => (
          <View key={kit.id} style={[styles.cell, { width: `${100 / columns}%` }]}>
            <KitCard kit={kit} />
          </View>
        ))}
        <View style={[styles.cell, { width: `${100 / columns}%` }]}>
          <NewKit />
        </View>
      </View>
    </ScrollView>
  );
}

function KitCard({ kit }: { kit: Kit }) {
  const { c } = useTheme();
  const router = useRouter();
  const { setKitId } = useSession();

  // The kit's mark, once the logo model has made one. eidolon-logo-1 is still
  // training, so most kits will legitimately have nothing here yet.
  const { data: jobs } = useJobHistory();
  const markJob = useMemo(
    () => jobs?.find((j) => j.kind === "logo" && j.status === "done"),
    [jobs],
  );
  const markUri = useJobCover(markJob?.job_id ?? "");

  return (
    <View style={[styles.card, { backgroundColor: c.sf }]}>
      <Display size={17}>{kit.name}</Display>

      <View style={styles.swatches}>
        {kit.palette.map((hex) => (
          <View key={hex} style={[styles.swatch, { backgroundColor: hex }]} />
        ))}
      </View>

      <Mono size={type.monoSM} color={c.t2}>
        {kit.fonts}
      </Mono>

      <View style={styles.markRow}>
        <View style={[styles.markTile, { backgroundColor: c.sf0 }]}>
          {markUri ? <Image source={{ uri: markUri }} resizeMode="cover" style={styles.fill} /> : null}
        </View>
        <Mono size={10} color={c.t3}>
          {markUri ? "mark · eidolon-logo-1" : "no mark yet"}
        </Mono>
      </View>

      <Pill
        label="use in create"
        onPress={() => {
          setKitId(kit.id);
          router.push("/create");
        }}
      />
    </View>
  );
}

function NewKit() {
  const { c } = useTheme();
  return (
    <PressScale scale={0.98} style={[styles.newKit, { borderColor: c.ln2 }]}>
      <Icon name="folder" size={40} color={c.t2} />
      <Body size={type.bodySM} color={c.t2}>
        new kit
      </Body>
    </PressScale>
  );
}

const styles = StyleSheet.create({
  page: { paddingTop: 44, paddingBottom: 96, maxWidth: 1100, width: "100%", alignSelf: "center", gap: 26 },
  grid: { flexDirection: "row", flexWrap: "wrap", marginHorizontal: -7 },
  cell: { paddingHorizontal: 7, paddingBottom: 14 },
  fill: { width: "100%", height: "100%" },

  card: { borderRadius: radii.mediaLg, padding: 18, gap: 13 },
  swatches: { flexDirection: "row", gap: 6 },
  swatch: { width: 30, height: 30, borderRadius: 8 },
  markRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  markTile: { width: 52, height: 52, borderRadius: radii.media, overflow: "hidden" },

  newKit: {
    borderRadius: radii.mediaLg,
    borderWidth: 1,
    borderStyle: "dashed",
    minHeight: 220,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
});
