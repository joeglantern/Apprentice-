/** Chat - iterate on a piece by talking about it.
 *
 * The thread is the server's (hooks/useChat). This screen sends a message and renders
 * what comes back; it does not decide what a message means and it does not write the
 * assistant's lines. That used to happen here, which is why every reply was canned and
 * why free text always started a fresh poster instead of changing the open one.
 *
 * Two things the UI has to keep honest, because the backend guarantees them: a reply
 * is written before the render runs and only ever states an intent, and the `landed`
 * line underneath it - which appears later - is the only sentence that describes a
 * result. They are drawn differently for that reason.
 *
 * The versions rail on the right is the chain of jobs this thread produced, so going
 * back a step is picking v1 rather than undoing anything. */

import { useRouter } from "expo-router";
import { useMemo, useRef, useState } from "react";
import {
  Image,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";

import { DenoisingPreview } from "@/components/ui/DenoisingPreview";
import { Enter } from "@/components/ui/Enter";
import { Icon } from "@/components/ui/Icon";
import { JobArtwork } from "@/components/ui/JobArtwork";
import { Pill, QuickChip } from "@/components/ui/controls";
import { EidolonMark } from "@/components/ui/marks";
import { PressScale } from "@/components/ui/press";
import { Pulse } from "@/components/ui/Pulse";
import { useToast } from "@/components/ui/Toast";
import { Body, Mono, MonoLabel } from "@/components/ui/type";
import { useChat } from "@/hooks/useChat";
import { useArrivals } from "@/hooks/useArrivals";
import { useCancelJob } from "@/hooks/useCancelJob";
import { useGenerationProgress } from "@/hooks/useGenerationProgress";
import { useJob } from "@/hooks/useJob";
import { useJobCover } from "@/hooks/useJobCover";
import { readProgress } from "@/lib/progress";
import { isSubmitKey, noOutline } from "@/lib/styles";
import { radii, type } from "@/lib/tokens";
import type { ChatMessage, QuickAction } from "@/lib/types";
import { isTerminal } from "@/lib/types";
import { SIZE_PX, useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

const EMPTY = require("../../assets/brand/empty-chat.png");

/** The chips carry a known intent, so they travel as an action rather than as words
 * for a model to re-read: instant, free, and impossible to misroute. */
const QUICK: { label: string; action: QuickAction }[] = [
  { label: "swap photo", action: "swap_photo" },
  { label: "recompose", action: "recompose" },
];

export default function ChatScreen() {
  const { c, isDesktop } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const cancel = useCancelJob();

  const { activeJobId, setActiveJobId, kind, size, aesthetic } = useSession();
  const chat = useChat(activeJobId);

  const { data: job } = useJob(chat.activeJobId);
  const event = useGenerationProgress(chat.activeJobId);
  const progress = readProgress(job, event);

  const [draft, setDraft] = useState("");
  // Which version is being inspected, and which active piece that choice was made
  // under. Pairing the two makes "a new version supersedes the one you were looking
  // at" a derivation rather than an effect that resets state after the fact.
  const [viewing, setViewing] = useState<{ jobId: string; under: string | null } | null>(null);
  const scroller = useRef<ScrollView>(null);

  const shownJobId =
    viewing && viewing.under === chat.activeJobId ? viewing.jobId : chat.activeJobId;
  const cover = useJobCover(shownJobId ?? "");

  const arriving = useArrivals(
    useMemo(
      () => chat.messages.filter((m) => m.role !== "user").map((m) => m.message_id),
      [chat.messages],
    ),
  );

  const versions = useMemo(
    () => chat.messages.map((m) => m.job_id).filter((id): id is string => !!id),
    [chat.messages],
  );

  const turn = (message: string, quick?: QuickAction, onFailed?: () => void) => {
    if (chat.sending) return false;
    chat.send(
      {
        message,
        quick,
        aestheticVersion: aesthetic,
        kind,
        width: SIZE_PX[size][0],
        height: SIZE_PX[size][1],
      },
      { onError: onFailed },
    );
    return true;
  };

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    // Clear only once the send is actually going out, and hand the words back if the
    // request never lands. Clearing first meant a message typed while one was already
    // in flight was silently destroyed, and a failed send lost what you had written.
    if (!turn(text, undefined, () => setDraft((d) => (d ? d : text)))) return;
    Keyboard.dismiss();
    setDraft("");
  };

  const rendering = !!chat.activeJobId && !isTerminal(progress.status);
  const working = chat.sending || rendering;

  return (
    <View style={[styles.root, { flexDirection: isDesktop ? "row" : "column" }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.threadSide}
      >
        <ScrollView
          ref={scroller}
          onContentSizeChange={() => scroller.current?.scrollToEnd({ animated: true })}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          contentContainerStyle={styles.thread}
        >
          {chat.messages.length === 0 ? (
            <View style={styles.empty}>
              <Image source={EMPTY} style={styles.emptyGlyph} />
              <Body size={type.bodyMD} color={c.t2}>
                {chat.activeJobId ? "say what to change" : "describe something to make"}
              </Body>
              <Mono size={11} color={c.t3}>
                {chat.activeJobId ? "or use a quick action below" : "or start one in create"}
              </Mono>
            </View>
          ) : (
            <Mono size={type.monoXS} color={c.t4} style={styles.sessionHead}>
              {job?.prompt ? truncate(job.prompt, 46) : "session"}
            </Mono>
          )}

          {chat.messages.map((m) =>
            m.role === "user" ? (
              // The one in flight is dimmed rather than replaced, so when the server
              // returns its own copy nothing moves and the swap is invisible.
              <Enter
                key={m.message_id}
                disabled={m.message_id !== chat.pendingId}
                style={[
                  styles.userBubble,
                  { backgroundColor: c.raise, opacity: m.message_id === chat.pendingId ? 0.72 : 1 },
                ]}
              >
                <Body size={type.bodySM} style={styles.bubbleText}>
                  {m.text}
                </Body>
              </Enter>
            ) : (
              <Enter key={m.message_id} disabled={!arriving.has(m.message_id)}>
                <AssistantTurn message={m} onOpen={() => m.job_id && openCanvas(m.job_id)} />
              </Enter>
            ),
          )}

          {working ? (
            <View style={styles.turn}>
              <View style={styles.attribution}>
                <Pulse durationMs={1800}>
                  <EidolonMark size={15} color={c.accent} />
                </Pulse>
                <Mono size={type.monoXS} color={c.t3} style={styles.attributionText}>
                  eidolon · {chat.sending ? "reading that" : "working"}
                </Mono>
              </View>
              {rendering ? (
                <>
                  <DenoisingPreview
                    source={cover ? { uri: cover } : undefined}
                    pct={progress.pct}
                    style={styles.threadCard}
                  />
                  <View style={styles.workingLine}>
                    <Body size={10.5} color={c.t2}>
                      {progress.message}
                    </Body>
                    <Mono size={type.monoXS} color={c.accent}>
                      {progress.pct}%
                    </Mono>
                  </View>
                  <Pill
                    label={cancel.isPending ? "stopping" : "stop"}
                    height={24}
                    onPress={() => chat.activeJobId && cancel.mutate(chat.activeJobId)}
                    style={styles.stop}
                  />
                </>
              ) : null}
            </View>
          ) : null}

          {chat.error ? (
            <Body size={type.bodySM} color={c.t3}>
              that did not go through: {chat.error.message}
            </Body>
          ) : null}
        </ScrollView>

        <View style={styles.composerHost}>
          <View style={[styles.composer, { backgroundColor: c.sf, borderColor: c.raise2 }]}>
            <TextInput
              style={[styles.input, noOutline, { color: c.t1 }]}
              placeholder={chat.activeJobId ? "describe the change" : "describe the piece"}
              placeholderTextColor={c.t3}
              value={draft}
              onChangeText={setDraft}
              multiline
              onKeyPress={(e) => {
                if (isSubmitKey(e)) {
                  e.preventDefault?.();
                  send();
                }
              }}
              onSubmitEditing={send}
              blurOnSubmit={false}
            />
            <View style={styles.composerRow}>
              {chat.activeJobId
                ? QUICK.map((q) => (
                    <QuickChip
                      key={q.action}
                      label={q.label}
                      sunken
                      onPress={() => turn(q.label, q.action)}
                    />
                  ))
                : null}
              <PressScale
                scale={0.92}
                onPress={send}
                accessibilityRole="button"
                accessibilityLabel="send"
                style={[styles.send, { backgroundColor: c.accent }]}
              >
                <Icon name="arrowUp" size={16} color={c.bg0} strokeWidth={2} />
              </PressScale>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>

      {isDesktop ? (
        <View style={[styles.panel, { backgroundColor: c.void, borderLeftColor: c.ln }]}>
          <View style={styles.panelHead}>
            <MonoLabel>canvas</MonoLabel>
            <View style={styles.versions}>
              {versions.map((id, i) => {
                const on = shownJobId === id;
                return (
                  <PressScale
                    key={id}
                    scale={0.95}
                    onPress={() => setViewing({ jobId: id, under: chat.activeJobId })}
                    style={[styles.version, on && { backgroundColor: c.raise }]}
                  >
                    <Mono size={10} color={on ? c.t1 : c.t4}>
                      v{i + 1}
                    </Mono>
                  </PressScale>
                );
              })}
            </View>
          </View>

          <PressScale
            scale={0.99}
            disabled={!shownJobId}
            onPress={() => shownJobId && openCanvas(shownJobId)}
            style={[styles.panelArt, { backgroundColor: c.sf0 }]}
          >
            {shownJobId ? <JobArtwork jobId={shownJobId} kind={kind} fill style={styles.fill} /> : null}
          </PressScale>

          <Mono size={10} color={c.t4}>
            {job?.result?.aesthetic_version ?? aesthetic} · {size}
          </Mono>

          <View style={styles.panelActions}>
            <Pill label="export png" tone="accent" height={40} onPress={() => toast("exported png to photos")} />
            <Pill
              label="open in canvas"
              height={40}
              onPress={() => shownJobId && openCanvas(shownJobId)}
            />
          </View>
        </View>
      ) : null}
    </View>
  );

  function openCanvas(id: string) {
    setActiveJobId(id);
    router.push("/canvas");
  }
}

/** One assistant turn: the intent it stated, the render it produced, and - only once
 * that job has actually finished - what it turned out to be. The landed line is set
 * quieter than the reply because it arrives later and is not part of the exchange. */
function AssistantTurn({ message, onOpen }: { message: ChatMessage; onOpen: () => void }) {
  const { c } = useTheme();
  return (
    <View style={styles.turn}>
      <View style={styles.attribution}>
        <EidolonMark size={15} color={c.accent} />
        <Mono size={type.monoXS} color={c.t3} style={styles.attributionText}>
          eidolon
        </Mono>
      </View>
      <Body size={type.bodySM} style={styles.bubbleText}>
        {message.text}
      </Body>
      {message.job_id ? (
        <PressScale scale={0.98} onPress={onOpen} style={styles.threadCard}>
          <JobArtwork jobId={message.job_id} fill style={styles.fill} />
        </PressScale>
      ) : null}
      {message.landed ? (
        <Mono size={type.monoXS} color={c.t4}>
          {message.landed}
        </Mono>
      ) : null}
    </View>
  );
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : `${s.slice(0, n - 1)}…`;
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  fill: { width: "100%", height: "100%" },
  threadSide: { flex: 1, minWidth: 0 },
  thread: {
    maxWidth: 600,
    width: "100%",
    alignSelf: "center",
    paddingTop: 26,
    paddingHorizontal: 24,
    paddingBottom: 14,
    gap: 18,
  },
  sessionHead: { textAlign: "center", letterSpacing: 1, paddingBottom: 4 },
  userBubble: {
    alignSelf: "flex-end",
    maxWidth: "75%",
    borderRadius: radii.mediaLg,
    borderBottomRightRadius: 4,
    paddingVertical: 9,
    paddingHorizontal: 14,
  },
  turn: { maxWidth: "88%", gap: 9 },
  attribution: { flexDirection: "row", alignItems: "center", gap: 7 },
  attributionText: { letterSpacing: 0.8 },
  bubbleText: { lineHeight: type.bodySM * 1.55 },
  threadCard: { width: 212, aspectRatio: 1080 / 1350, borderRadius: radii.card, overflow: "hidden" },
  workingLine: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", width: 212 },
  stop: { alignSelf: "flex-start" },

  composerHost: { paddingHorizontal: 24, paddingBottom: 20, width: "100%", maxWidth: 600, alignSelf: "center" },
  composer: {
    borderWidth: 1,
    borderRadius: radii.deck,
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 10,
    gap: 9,
    shadowColor: "#000",
    shadowOpacity: 0.55,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 20 },
    elevation: 16,
  },
  input: {
    fontSize: 14,
    fontFamily: type.body.family,
    lineHeight: 21,
    paddingHorizontal: 4,
    paddingVertical: 2,
    minHeight: 24,
    textAlignVertical: "top",
  },
  composerRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  send: { marginLeft: "auto", width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center" },

  panel: { width: 340, flexShrink: 0, borderLeftWidth: 1, paddingVertical: 22, paddingHorizontal: 20, gap: 13 },
  panelHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  versions: { flexDirection: "row", gap: 4 },
  version: { borderRadius: radii.chip, paddingHorizontal: 9, paddingVertical: 3 },
  panelArt: { width: "100%", aspectRatio: 1080 / 1350, borderRadius: radii.card, overflow: "hidden" },
  panelActions: { marginTop: "auto", gap: 8 },

  empty: { paddingVertical: 60, alignItems: "center", gap: 8 },
  emptyGlyph: { width: 56, height: 56, opacity: 0.8, marginBottom: 4 },
});
