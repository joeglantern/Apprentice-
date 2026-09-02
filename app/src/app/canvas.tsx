/** Canvas detail - one piece, taken apart.
 *
 * The artwork sits on pure black (the only place in the app that is not the near-
 * black background: media gets the OLED treatment), and the panel beside it is the
 * only surface that explains the model's reasoning. Selecting a layer draws its box
 * on the artwork, so "headline" means a place on the page, not a row in a list. */

import { useLocalSearchParams, useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { Icon } from "@/components/ui/Icon";
import { JobArtwork } from "@/components/ui/JobArtwork";
import { Pill } from "@/components/ui/controls";
import { PressScale } from "@/components/ui/press";
import { useToast } from "@/components/ui/Toast";
import { Body, Mono, MonoLabel } from "@/components/ui/type";
import { useJob } from "@/hooks/useJob";
import { useRevise } from "@/hooks/useRevise";
import { radii, type } from "@/lib/tokens";
import type { Layer, LayerType } from "@/lib/types";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

const COMPOSITIONS = ["anchor", "centered", "split"] as const;
const TYPEFACES = ["inter", "bebas", "playfair", "grotesk"] as const;

/** Two letters, so a dense list still parses at a glance. */
const TAG: Record<LayerType, string> = { text: "tx", image: "im", icon: "ic", shape: "sh" };
const ACTION: Record<LayerType, string> = {
  text: "edit text",
  image: "regenerate zone",
  icon: "swap icon",
  shape: "recolor",
};

export default function CanvasScreen() {
  const { c, isDesktop } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const revise = useRevise();

  // Reachable both ways: pushed from explore via session, or linked with ?jobId=.
  const params = useLocalSearchParams<{ jobId?: string }>();
  const { activeJobId, setActiveJobId } = useSession();
  const jobId = params.jobId ?? activeJobId;

  const { data: job } = useJob(jobId ?? null);
  const [selected, setSelected] = useState(-1);

  const layers = useMemo(
    () => (job?.result?.layers ?? []).filter((l) => l.visible !== false).sort((a, b) => b.z_index - a.z_index),
    [job],
  );

  // A poster whose photo render timed out still comes back "done" - the layout is
  // real, the picture is a placeholder block. Say so, rather than letting it read
  // as a design that just looks broken.
  const photoMissing =
    job?.status === "done" &&
    layers.some((l) => l.type === "image" && !l.raster_key);

  const canvasW = job?.result?.canvas_width ?? 1;
  const canvasH = job?.result?.canvas_height ?? 1;
  const aspect = canvasW / canvasH;
  const highlight = selected >= 0 ? layers[selected] : undefined;

  const applyRevise = (changes: Parameters<typeof revise.mutate>[0]["changes"]) => {
    if (!jobId) return;
    revise.mutate(
      { jobId, changes },
      {
        onSuccess: (accepted) => {
          setActiveJobId(accepted.job_id);
          setSelected(-1);
        },
      },
    );
  };

  return (
    <View style={[styles.root, { flexDirection: isDesktop ? "row" : "column" }]}>
      <View style={[styles.media, { backgroundColor: c.mediaBg }]}>
        <PressScale scale={0.99} onPress={() => router.back()} style={styles.back}>
          <Icon name="arrowLeft" size={15} color={c.t2} opacity={0.6} />
          <Body size={13} color={c.t2}>
            back
          </Body>
        </PressScale>

        <View style={styles.mediaBody}>
          <View style={[styles.artwork, { aspectRatio: aspect }]}>
            <JobArtwork jobId={jobId ?? ""} kind={job?.kind} fill style={styles.artworkImg} />
            {highlight ? <Highlight layer={highlight} canvasW={canvasW} canvasH={canvasH} /> : null}
          </View>
        </View>
      </View>

      <ScrollView
        style={[
          styles.panel,
          isDesktop ? { width: 340, borderLeftWidth: 1, borderLeftColor: c.ln2 } : undefined,
        ]}
        contentContainerStyle={styles.panelBody}
      >
        <Body size={14.5} style={styles.prompt}>
          {job?.prompt ?? ""}
        </Body>

        <View style={styles.metaRow}>
          {[
            job?.result?.aesthetic_version,
            job?.kind,
            job?.result ? `${canvasW}×${canvasH}` : undefined,
          ]
            .filter(Boolean)
            .map((m) => (
              <View key={m} style={[styles.metaChip, { backgroundColor: c.sf }]}>
                <Mono size={type.monoSM} color={c.t2}>
                  {m}
                </Mono>
              </View>
            ))}
          {photoMissing ? (
            <View style={[styles.metaChip, { backgroundColor: c.sf }]}>
              <Mono size={type.monoSM} color={c.error}>
                photo did not render
              </Mono>
            </View>
          ) : null}
        </View>

        {layers.length ? (
          <View style={styles.block}>
            <MonoLabel>layers</MonoLabel>
            {layers.map((l, i) => {
              const on = selected === i;
              return (
                <PressScale
                  key={l.layer_id}
                  scale={0.99}
                  onPress={() => setSelected(on ? -1 : i)}
                  style={[styles.layerRow, { backgroundColor: on ? c.raise : c.sf0 }]}
                >
                  <View style={[styles.layerTag, { backgroundColor: c.raise }]}>
                    <Mono size={9} color={on ? c.accent : c.t3} style={styles.layerTagText}>
                      {TAG[l.type]}
                    </Mono>
                  </View>
                  <Body size={13} numberOfLines={1} style={styles.grow}>
                    {l.name}
                  </Body>
                  <Body size={11} color={c.t3}>
                    {ACTION[l.type]}
                  </Body>
                </PressScale>
              );
            })}
          </View>
        ) : null}

        <View style={styles.block}>
          <MonoLabel>adjust</MonoLabel>
          <View style={styles.chipRow}>
            {COMPOSITIONS.map((comp) => {
              const on = job?.plan?.composition === comp;
              return (
                <PressScale
                  key={comp}
                  scale={0.96}
                  disabled={revise.isPending}
                  onPress={() => applyRevise({ composition: comp })}
                  style={[styles.adjChip, { backgroundColor: on ? c.t1 : c.sf }]}
                >
                  <Body size={12} weight={on ? "500" : "400"} color={on ? c.bg0 : c.t2}>
                    {comp}
                  </Body>
                </PressScale>
              );
            })}
            <PressScale
              scale={0.96}
              disabled={revise.isPending}
              onPress={() => applyRevise({ rerender_photo: true })}
              style={[styles.adjChip, { backgroundColor: c.sf }]}
            >
              <Body size={12} color={c.t2}>
                new photo
              </Body>
            </PressScale>
          </View>

          <View style={styles.chipRow}>
            {TYPEFACES.map((tf) => {
              const on = job?.plan?.typeface === tf;
              return (
                <PressScale
                  key={tf}
                  scale={0.96}
                  disabled={revise.isPending}
                  onPress={() => applyRevise({ typeface: tf })}
                  style={[styles.adjChip, { backgroundColor: on ? c.t1 : c.sf }]}
                >
                  <Mono size={11} weight={on ? "500" : "400"} color={on ? c.bg0 : c.t2}>
                    {tf}
                  </Mono>
                </PressScale>
              );
            })}
          </View>
        </View>

        {job?.plan?.rationale ? (
          <View style={styles.block}>
            <MonoLabel>why this design</MonoLabel>
            <Body size={12.5} color={c.t2} style={styles.rationale}>
              {job.plan.rationale}
            </Body>
          </View>
        ) : null}

        <View style={styles.actions}>
          <Pill label="export png" tone="accent" height={44} onPress={() => toast("exported png to photos")} />
          <Pill
            label="remix"
            height={44}
            onPress={() => router.push("/create")}
          />
        </View>
      </ScrollView>
    </View>
  );
}

/** The selected layer's own box, drawn over the artwork in canvas coordinates. */
function Highlight({ layer, canvasW, canvasH }: { layer: Layer; canvasW: number; canvasH: number }) {
  const { c } = useTheme();
  const { x, y, width, height } = layer.bbox;
  return (
    <View
      pointerEvents="none"
      style={[
        styles.highlight,
        {
          borderColor: c.accent,
          left: `${(x / canvasW) * 100}%`,
          top: `${(y / canvasH) * 100}%`,
          width: `${(width / canvasW) * 100}%`,
          height: `${(height / canvasH) * 100}%`,
        },
      ]}
    >
      <View style={[styles.highlightTag, { backgroundColor: c.accent }]}>
        <Mono size={9} color={c.bg0}>
          {layer.name}
        </Mono>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  grow: { flex: 1, minWidth: 0 },

  media: { flex: 1, minWidth: 0 },
  back: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 20, height: 48 },
  mediaBody: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 36, paddingBottom: 36, minHeight: 320 },
  // Takes the full height of the stage and derives its width from the canvas
  // aspect. Without an explicit height, a box with only aspectRatio and max
  // constraints has nothing to size from and collapses to its intrinsic width.
  artwork: { height: "100%", maxWidth: "100%", position: "relative" },
  artworkImg: { width: "100%", height: "100%", borderRadius: 6 },
  highlight: { position: "absolute", borderWidth: 1.5, borderRadius: 4 },
  highlightTag: { position: "absolute", top: -22, left: -1.5, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },

  panel: { flexGrow: 0 },
  panelBody: { paddingVertical: 28, paddingHorizontal: 22, gap: 22 },
  prompt: { lineHeight: 14.5 * 1.5 },
  metaRow: { flexDirection: "row", gap: 6, flexWrap: "wrap" },
  metaChip: { borderRadius: 5, paddingHorizontal: 8, paddingVertical: 5 },
  block: { gap: 6 },
  layerRow: { flexDirection: "row", alignItems: "center", gap: 10, padding: 10, borderRadius: radii.thumb },
  layerTag: { borderRadius: 3, paddingHorizontal: 5, paddingVertical: 2 },
  layerTagText: { letterSpacing: 0.5 },
  chipRow: { flexDirection: "row", gap: 6, flexWrap: "wrap" },
  adjChip: { borderRadius: radii.chip, paddingHorizontal: 13, paddingVertical: 6 },
  rationale: { lineHeight: 12.5 * 1.6 },
  actions: { gap: 8, marginTop: "auto" },
});
