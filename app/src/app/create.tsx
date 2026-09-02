/** Create - the showpiece.
 *
 * A full-bleed void stage with one floating deck. Everything you can decide lives
 * in the deck; everything the model is doing lives on the stage. The stage is never
 * empty of meaning: idle it breathes, running it shows the piece resolving out of
 * noise, done it is just the work. */

import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  Image,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";

import { DenoisingPreview } from "@/components/ui/DenoisingPreview";
import { Enter } from "@/components/ui/Enter";
import { Icon } from "@/components/ui/Icon";
import { JobArtwork } from "@/components/ui/JobArtwork";
import { OutlineChip, Pill, Segmented } from "@/components/ui/controls";
import { EidolonMark } from "@/components/ui/marks";
import { PressScale } from "@/components/ui/press";
import { Pulse } from "@/components/ui/Pulse";
import { useToast } from "@/components/ui/Toast";
import { Body, Mono } from "@/components/ui/type";
import { VoidStage } from "@/components/ui/VoidStage";
import { useAesthetics } from "@/hooks/useAesthetics";
import { useCancelJob } from "@/hooks/useCancelJob";
import { useSessionGenerate } from "@/hooks/useSessionGenerate";
import { useThread } from "@/hooks/useThread";
import { useGenerationProgress } from "@/hooks/useGenerationProgress";
import { useJob } from "@/hooks/useJob";
import { useJobCover } from "@/hooks/useJobCover";
import { useJobHistory } from "@/hooks/useJobHistory";
import { KITS, findKit } from "@/lib/kits";
import { readProgress } from "@/lib/progress";
import { isSubmitKey, noOutline } from "@/lib/styles";
import { radii, type } from "@/lib/tokens";
import type { JobKind } from "@/lib/types";
import { SIZE_PX, useSession, type SizeKey } from "@/state/session";
import { useTheme } from "@/theme/theme";

const KIND_OPTIONS: { value: JobKind; label: string }[] = [
  { value: "poster", label: "poster" },
  { value: "image", label: "photo" },
  { value: "logo", label: "logo" },
];

const SIZE_OPTIONS: { value: SizeKey; label: string }[] = (
  ["1:1", "4:5", "16:9", "9:16"] as SizeKey[]
).map((s) => ({ value: s, label: s }));

export default function CreateScreen() {
  const { c, isDesktop } = useTheme();
  const { height } = useWindowDimensions();
  const router = useRouter();
  const toast = useToast();

  const { kind, setKind, size, setSize, aesthetic, setAesthetic, kitId, setKitId, activeJobId, setActiveJobId, newSession } =
    useSession();

  const [prompt, setPrompt] = useState("");
  // What was asked for, kept so the stage can echo it and a failed request can hand
  // the words back to the deck.
  const [asked, setAsked] = useState("");
  const generate = useSessionGenerate();
  const cancel = useCancelJob();
  const session = useThread(activeJobId);

  const { data: job } = useJob(activeJobId);
  const event = useGenerationProgress(activeJobId);
  const progress = readProgress(job, event);
  const cover = useJobCover(activeJobId ?? "");

  const aspect = useMemo(() => {
    const [w, h] = SIZE_PX[size];
    return w / h;
  }, [size]);

  const phase = !activeJobId
    ? "idle"
    : progress.status === "done"
      ? "done"
      : progress.status === "error"
        ? "error"
        : progress.status === "cancelled"
          ? "cancelled"
          : "running";

  const submit = () => {
    const text = prompt.trim();
    if (text.length < 3 || generate.isPending) return;
    // Get out of the way so the stage is visible the moment work starts.
    Keyboard.dismiss();
    setAsked(text);
    setPrompt("");
    generate.mutate(
      {
        prompt: text,
        aestheticVersion: aesthetic,
        kind,
        size: SIZE_PX[size],
        brand: findKit(kitId),
      },
      // The request never landed, so hand the words back rather than eating them.
      { onError: () => setPrompt((d) => (d ? d : text)) },
    );
  };

  const runs = useMemo(
    () => Array.from(new Set(session.messages.map((m) => m.job_id).filter((id): id is string => !!id))),
    [session.messages],
  );
  const shown = activeJobId;

  const stageH = Math.min(height * 0.52, 480);

  return (
    <VoidStage>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.fill}
      >
        <Pressable
          style={[styles.stage, isDesktop && styles.stageFloatingDeck]}
          onPress={Keyboard.dismiss}
          accessible={false}
        >
          {phase === "idle" ? (
            <Enter style={styles.idle}>
              <Pulse durationMs={3500} min={0.35}>
                <EidolonMark size={52} color={c.accent} />
              </Pulse>
              <Mono size={11} color={c.t4}>
                describe the piece. eidolon does the rest.
              </Mono>
            </Enter>
          ) : null}

          {phase === "running" ? (
            <Enter style={styles.running}>
              {asked ? (
                <Body size={13.5} color={c.t2} numberOfLines={2} style={styles.echo}>
                  {asked}
                </Body>
              ) : null}
              <DenoisingPreview
                source={cover ? { uri: cover } : undefined}
                pct={progress.pct}
                style={[styles.preview, { height: stageH, aspectRatio: aspect, shadowColor: c.accent }]}
              />
              <View style={styles.statusRow}>
                <Body size={13} color={c.t2}>
                  {progress.message}
                </Body>
                <Mono size={10} color={c.accent}>
                  {progress.pct}%
                </Mono>
                <Pill
                  label={cancel.isPending ? "stopping" : "stop"}
                  height={26}
                  onPress={() => activeJobId && cancel.mutate(activeJobId)}
                />
              </View>
            </Enter>
          ) : null}

          {phase === "done" ? (
            <Enter style={styles.running}>
              {activeJobId ? (
                <JobArtwork
                  jobId={activeJobId}
                  kind={kind}
                  fill
                  style={[styles.result, { height: Math.min(height * 0.56, 520), aspectRatio: aspect }]}
                />
              ) : null}
              <View style={styles.metaRow}>
                <Mono size={10} color={c.t3}>
                  {aesthetic} · {size}
                </Mono>
                <Pill
                  label="remix"
                  height={30}
                  onPress={() => {
                    if (job) setPrompt(job.prompt);
                    setActiveJobId(null);
                  }}
                />
                <Pill label="open in canvas" height={30} onPress={() => router.push("/canvas")} />
                <Pill label="export png" height={30} tone="accent" onPress={() => toast("exported png to photos")} />
              </View>

              {runs.length > 1 ? (
                <View style={styles.runs}>
                  {runs.map((id, i) => {
                    const on = id === shown;
                    return (
                      <PressScale
                        key={id}
                        scale={0.95}
                        onPress={() => setActiveJobId(id)}
                        accessibilityRole="button"
                        accessibilityState={{ selected: on }}
                        style={[styles.run, on && { backgroundColor: c.raise }]}
                      >
                        <Mono size={10} color={on ? c.t1 : c.t4}>
                          v{i + 1}
                        </Mono>
                      </PressScale>
                    );
                  })}
                  <Pill label="new session" height={26} onPress={newSession} style={styles.newSession} />
                </View>
              ) : null}
            </Enter>
          ) : null}

          {phase === "cancelled" ? (
            <Enter style={styles.idle}>
              <Body size={type.bodyMD} color={c.t2}>
                stopped
              </Body>
              <Mono size={11} color={c.t4}>
                nothing was charged to the queue past this point
              </Mono>
              <Pill label="start again" height={32} onPress={() => setActiveJobId(null)} />
            </Enter>
          ) : null}

          {phase === "error" ? (
            <View style={styles.idle}>
              <Body size={type.bodyMD} color={c.error}>
                {job?.error ?? "that one failed"}
              </Body>
              <Pill label="try again" height={32} onPress={() => setActiveJobId(null)} />
            </View>
          ) : null}

          {/* The request never even landed - wrong address, no tunnel, dead server. */}
          {generate.isError ? (
            <View style={styles.idle}>
              <Body size={type.bodyMD} color={c.error}>
                could not send that
              </Body>
              <Mono size={11} color={c.t3} style={styles.errorReason}>
                {(generate.error as Error).message}
              </Mono>
              <Mono size={11} color={c.t3}>
                check the address under settings
              </Mono>
            </View>
          ) : null}
        </Pressable>

        {/* Desktop keeps the design's floating deck over a full-bleed stage. On a
            phone it sits in normal flow instead, because an absolutely positioned
            deck is exactly what KeyboardAvoidingView cannot lift - the keyboard
            covered it and there was no way to dismiss it. */}
        <View
          style={[
            styles.deckHost,
            { paddingHorizontal: isDesktop ? 0 : 12 },
            isDesktop && styles.deckHostFloating,
          ]}
        >
          <View
            style={[
              styles.deck,
              { backgroundColor: c.sf, borderColor: c.raise2, maxWidth: isDesktop ? 680 : undefined },
            ]}
          >
            <TextInput
              style={[styles.prompt, noOutline, { color: c.t1 }]}
              placeholder="poster for a summer jazz festival, friday night, downtown park"
              placeholderTextColor={c.t3}
              value={prompt}
              onChangeText={setPrompt}
              multiline
              numberOfLines={2}
              // Enter generates, shift+enter makes a new line. A multiline input
              // never fires onSubmitEditing, so the key is read directly.
              onKeyPress={(e) => {
                if (isSubmitKey(e)) {
                  e.preventDefault?.();
                  submit();
                }
              }}
              onSubmitEditing={submit}
              blurOnSubmit={false}
            />

            {/* Generate sits outside the scroller so it is always reachable: on
                phone the chips scroll sideways rather than stacking the deck four
                rows deep, and a button inside that would scroll out of reach. */}
            <View style={styles.controlsBar}>
              <ScrollView
                horizontal={!isDesktop}
                showsHorizontalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
                style={styles.controlsScroller}
                contentContainerStyle={[styles.controls, !isDesktop && styles.controlsRow]}
              >
                <Segmented options={KIND_OPTIONS} value={kind} onChange={setKind} />
                <Segmented options={SIZE_OPTIONS} value={size} onChange={setSize} mono />

                <OutlineChip label="no kit" selected={kitId === "none"} onPress={() => setKitId("none")} />
                {KITS.map((k) => (
                  <OutlineChip
                    key={k.id}
                    label={k.name}
                    selected={kitId === k.id}
                    onPress={() => setKitId(k.id)}
                    leading={
                      <View style={styles.swatches}>
                        {k.palette.slice(0, 4).map((hex) => (
                          <View key={hex} style={[styles.swatch, { backgroundColor: hex }]} />
                        ))}
                      </View>
                    }
                  />
                ))}

                <AestheticChips selected={aesthetic} onSelect={setAesthetic} />
              </ScrollView>

              <PressScale
                scale={0.92}
                onPress={submit}
                accessibilityRole="button"
                accessibilityLabel="generate"
                disabled={generate.isPending}
                style={[styles.go, { backgroundColor: c.accent, opacity: generate.isPending ? 0.5 : 1 }]}
              >
                {generate.isPending ? (
                  <Pulse durationMs={1200}>
                    <EidolonMark size={18} color={c.bg0} />
                  </Pulse>
                ) : (
                  <Icon name="arrowUp" size={18} color={c.bg0} strokeWidth={2} />
                )}
              </PressScale>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </VoidStage>
  );
}

/** One chip per trained aesthetic. Baseline wears the Eidolon mark; a trained one
 * wears its own most recent finished piece, which is a truer sample than a stock
 * thumbnail would be. */
function AestheticChips({ selected, onSelect }: { selected: string; onSelect: (v: string) => void }) {
  const { data } = useAesthetics();
  const { data: jobs } = useJobHistory();

  const list = data?.length ? data : [{ version: "baseline", label: "baseline", kind: "style" }];

  // A selection the server does not offer would be rejected at generate time.
  // This is the only place that knows the real list, so it reconciles here.
  useEffect(() => {
    if (data?.length && !data.some((a) => a.version === selected)) {
      onSelect(data[0].version);
    }
  }, [data, selected, onSelect]);

  return (
    <>
      {list.map((a) => {
        const sample = jobs?.find((j) => j.status === "done" && j.aesthetic_version === a.version);
        return (
          <AestheticChip
            key={a.version}
            version={a.version}
            label={a.label || a.version}
            sampleJobId={sample?.job_id}
            selected={selected === a.version}
            onPress={() => onSelect(a.version)}
          />
        );
      })}
    </>
  );
}

function AestheticChip({
  version,
  label,
  sampleJobId,
  selected,
  onPress,
}: {
  version: string;
  label: string;
  sampleJobId?: string;
  selected: boolean;
  onPress: () => void;
}) {
  const { c } = useTheme();
  const uri = useJobCover(sampleJobId ?? "");

  return (
    <OutlineChip
      label={label}
      selected={selected}
      onPress={onPress}
      leading={
        <View style={[styles.thumb, { backgroundColor: c.raise2 }]}>
          {uri ? (
            <Image source={{ uri }} resizeMode="cover" style={styles.thumbImg} />
          ) : version === "baseline" ? (
            <EidolonMark size={16} color={c.accent} />
          ) : null}
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  stage: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 32, paddingTop: 32, paddingBottom: 24 },
  stageFloatingDeck: { paddingBottom: 220 },
  idle: { alignItems: "center", gap: 14 },
  echo: { textAlign: "center", maxWidth: 520 },
  runs: { flexDirection: "row", alignItems: "center", gap: 4, flexWrap: "wrap", justifyContent: "center" },
  run: { borderRadius: radii.chip, paddingHorizontal: 9, paddingVertical: 3 },
  newSession: { marginLeft: 6 },
  errorReason: { textAlign: "center", paddingHorizontal: 24 },
  running: { alignItems: "center", gap: 16, maxWidth: "100%" },
  preview: {
    maxWidth: "100%",
    borderRadius: radii.card,
    shadowOpacity: 0.35,
    shadowRadius: 60,
    shadowOffset: { width: 0, height: 0 },
  },
  result: { maxWidth: "100%", borderRadius: radii.control },
  statusRow: { flexDirection: "row", alignItems: "baseline", gap: 12 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap", justifyContent: "center" },

  deckHost: { alignItems: "center", paddingBottom: 24 },
  deckHostFloating: { position: "absolute", left: 0, right: 0, bottom: 24, paddingBottom: 0 },
  deck: {
    width: "100%",
    borderWidth: 1,
    borderRadius: radii.deck,
    paddingHorizontal: 14,
    paddingTop: 14,
    paddingBottom: 12,
    gap: 10,
    shadowColor: "#000",
    shadowOpacity: 0.7,
    shadowRadius: 40,
    shadowOffset: { width: 0, height: 24 },
    elevation: 20,
  },
  prompt: {
    fontSize: 15,
    fontFamily: type.body.family,
    lineHeight: 22,
    paddingHorizontal: 4,
    paddingVertical: 2,
    minHeight: 44,
    textAlignVertical: "top",
  },
  controlsBar: { flexDirection: "row", alignItems: "center", gap: 8 },
  // flex + minWidth 0 so the scroller measures against the deck, not its content.
  controlsScroller: { flex: 1, minWidth: 0, flexGrow: 1 },
  controls: { flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" },
  controlsRow: { flexWrap: "nowrap", paddingRight: 4 },
  swatches: { flexDirection: "row", gap: 2 },
  swatch: { width: 9, height: 9, borderRadius: 3 },
  thumb: { width: 22, height: 22, borderRadius: 11, overflow: "hidden", alignItems: "center", justifyContent: "center" },
  thumbImg: { width: "100%", height: "100%" },
  go: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", flexShrink: 0 },
});
