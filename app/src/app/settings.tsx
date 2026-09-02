/** Settings - all read-only. Nothing here is a switch, because nothing here is
 * this app's to change: the server and token come from the build, capture consent
 * is the collector's to grant on the studio mac, and the pipeline is the backend's.
 *
 * Two sections (capture consent, pipeline) have no endpoint to read yet, so they
 * say so rather than printing plausible values. A settings screen that quietly
 * lies about what a server is running is worse than one that admits it cannot see. */

import { Alert, Image, Platform, ScrollView, StyleSheet, View } from "react-native";

import { Pill } from "@/components/ui/controls";
import { Body, Display, Mono, MonoLabel } from "@/components/ui/type";
import { useAesthetics } from "@/hooks/useAesthetics";
import { useServerHealth } from "@/hooks/useServerHealth";
import { useSession } from "@/state/session";
import { useRouter } from "expo-router";

import { authToken, socketBaseUrl } from "@/lib/api";
import { radii, type } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

const APP_ICON = require("../../assets/brand/app-icon.png");

const SHORTCUTS: [string, string][] = [
  ["generate", "enter"],
  ["focus prompt", "/"],
  ["new line", "shift + enter"],
];

export default function SettingsScreen() {
  const { c, isDesktop } = useTheme();
  const router = useRouter();
  const { data: aesthetics } = useAesthetics();
  const health = useServerHealth();
  const { signOut } = useSession();

  const leave = async () => {
    await signOut();
    router.replace("/auth");
  };

  const confirmLeave = () => {
    if (Platform.OS === "web") return void leave();
    Alert.alert(
      "sign out",
      "this also clears the saved server address and token, so you will set them again next time.",
      [
        { text: "cancel", style: "cancel" },
        { text: "sign out", style: "destructive", onPress: () => void leave() },
      ],
    );
  };

  return (
    <ScrollView contentContainerStyle={[styles.page, { paddingHorizontal: isDesktop ? 32 : 20 }]}>
      <Display size={isDesktop ? type.displayLG : 36}>settings</Display>

      <Section label="server">
        <Card>
          <Row label="api base url" value={socketBaseUrl() || "not set"} />
          <Divider />
          <View style={styles.themeRow}>
            <Body size={type.bodySM}>reachable</Body>
            <View style={styles.themeValue}>
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor: health.isLoading
                      ? c.t3
                      : health.isSuccess
                        ? c.success
                        : c.error,
                  },
                ]}
              />
              <Body size={13} color={c.t2}>
                {health.isLoading ? "checking" : health.isSuccess ? "yes" : "no"}
              </Body>
            </View>
          </View>
          {health.isError ? (
            <Body size={11.5} color={c.t3}>
              nothing answered at that address. on a phone, localhost means the phone
              itself, not the machine running the server.
            </Body>
          ) : null}
        </Card>
      </Section>

      <Section label="account">
        <Card>
          <Row label="agent" value="app" />
          <Divider />
          <Row label="token" value={maskToken(authToken())} />
          <Divider />
          <Pill label="sign out" onPress={confirmLeave} />
        </Card>
      </Section>

      <Section label="capture consent">
        <Card>
          <View style={styles.consentHead}>
            <View style={[styles.dot, { backgroundColor: c.t3 }]} />
            <Body size={type.bodySM}>collector status not reported</Body>
          </View>
          <Body size={12.5} color={c.t2} style={styles.consentBody}>
            this server does not expose the collector&apos;s state yet, so the app cannot show what is
            being watched or when it last synced.
          </Body>
          <Body size={11} color={c.t3}>
            read only. change this on the collector, not here.
          </Body>
        </Card>
      </Section>

      <Section label="models">
        <Card tight>
          {(aesthetics ?? []).map((a, i, arr) => (
            <Row
              key={a.version}
              mono
              label={a.version}
              value={a.trained_on ? `${a.trained_on} images` : "no training"}
              last={i === arr.length - 1}
            />
          ))}
          {!aesthetics?.length ? <Row mono label="baseline" value="no training" last /> : null}
        </Card>
      </Section>

      <Section label="pipeline">
        <Card>
          <Body size={12.5} color={c.t2}>
            this server does not report its director, renderer or detail-pass configuration yet.
          </Body>
        </Card>
      </Section>

      <Section label="appearance">
        <Card>
          <View style={styles.themeRow}>
            <Body size={type.bodySM}>theme</Body>
            <View style={styles.themeValue}>
              <Body size={13} color={c.t2}>
                space black
              </Body>
              <View style={[styles.tag, { backgroundColor: c.raise }]}>
                <Mono size={9} color={c.t3} style={styles.tagText}>
                  DEFAULT
                </Mono>
              </View>
            </View>
          </View>
        </Card>
      </Section>

      <Section label="shortcuts">
        <Card tight>
          {SHORTCUTS.map(([label, key], i) => (
            <View
              key={label}
              style={[styles.keyRow, i < SHORTCUTS.length - 1 && { borderBottomColor: c.ln, borderBottomWidth: 1 }]}
            >
              <Body size={13}>{label}</Body>
              <View style={[styles.key, { backgroundColor: c.raise }]}>
                <Mono size={10} color={c.t2}>
                  {key}
                </Mono>
              </View>
            </View>
          ))}
        </Card>
        <Body size={11} color={c.t4} style={styles.note}>
          shortcuts apply where a hardware keyboard exists
        </Body>
      </Section>

      <Section label="about">
        <Card>
          <View style={styles.aboutRow}>
            <View style={styles.aboutLeft}>
              <Image source={APP_ICON} style={styles.aboutIcon} />
              <Body size={13}>umbra</Body>
            </View>
            <Mono size={type.monoSM} color={c.t3}>
              0.4.2 · one codebase · ios / android / web
            </Mono>
          </View>
        </Card>
      </Section>
    </ScrollView>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <MonoLabel>{label}</MonoLabel>
      {children}
    </View>
  );
}

function Card({ children, tight }: { children: React.ReactNode; tight?: boolean }) {
  const { c } = useTheme();
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: c.sf },
        tight ? styles.cardTight : styles.cardPadded,
      ]}
    >
      {children}
    </View>
  );
}

function Row({
  label,
  value,
  mono,
  last,
}: {
  label: string;
  value: string;
  mono?: boolean;
  last?: boolean;
}) {
  const { c } = useTheme();
  const Label = mono ? Mono : Body;
  return (
    <View
      style={[
        styles.row,
        mono && styles.rowTight,
        mono && !last && { borderBottomColor: c.ln, borderBottomWidth: 1 },
      ]}
    >
      <Label size={mono ? type.monoMD : type.bodySM} color={c.t1} numberOfLines={1}>
        {label}
      </Label>
      <Body size={11.5} color={c.t2} numberOfLines={1} style={styles.value}>
        {value}
      </Body>
    </View>
  );
}

function Divider() {
  const { c } = useTheme();
  return <View style={[styles.divider, { backgroundColor: c.raise }]} />;
}

/** Enough of the token to recognise which one is in use, never enough to reuse. */
function maskToken(token?: string): string {
  if (!token) return "not set";
  if (token.length <= 8) return "····";
  return `${token.slice(0, 3)}····${token.slice(-4)}`;
}

const styles = StyleSheet.create({
  page: { paddingTop: 44, paddingBottom: 96, maxWidth: 620, width: "100%", alignSelf: "center", gap: 28 },
  section: { gap: 8 },
  card: { borderRadius: radii.card },
  cardPadded: { paddingVertical: 15, paddingHorizontal: 17, gap: 11 },
  cardTight: { paddingHorizontal: 17, paddingVertical: 6 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  rowTight: { paddingVertical: 10 },
  value: { flexShrink: 1, textAlign: "right" },
  divider: { height: 1 },
  consentHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  consentBody: { lineHeight: 12.5 * 1.65 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  themeRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  themeValue: { flexDirection: "row", alignItems: "center", gap: 8 },
  tag: { borderRadius: 4, paddingHorizontal: 7, paddingVertical: 3 },
  tagText: { letterSpacing: 1 },
  keyRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 9 },
  key: { borderRadius: 5, paddingHorizontal: 8, paddingVertical: 3 },
  note: { paddingHorizontal: 2 },
  aboutRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  aboutLeft: { flexDirection: "row", alignItems: "center", gap: 11 },
  aboutIcon: { width: 32, height: 32, borderRadius: 8 },
});
