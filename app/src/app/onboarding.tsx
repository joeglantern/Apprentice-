/** First run, once. Points the app at a studio server and states plainly where
 * capture happens - the collector runs on the studio mac and this app only reads
 * its status, which is the one thing a person should not have to go digging for. */

import { useRouter } from "expo-router";
import { useState } from "react";
import { Image, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, TextInput, View } from "react-native";

import { PressScale } from "@/components/ui/press";
import { Body, Display, Mono, MonoLabel } from "@/components/ui/type";
import { VoidStage } from "@/components/ui/VoidStage";
import { defaultBaseUrl } from "@/lib/api";
import { radii, type } from "@/lib/tokens";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

const APP_ICON = require("../../assets/brand/app-icon.png");

export default function OnboardingScreen() {
  const { c } = useTheme();
  const router = useRouter();
  const { completeOnboarding } = useSession();

  const [server, setServer] = useState(defaultBaseUrl());
  const [token, setToken] = useState("");

  const enter = async () => {
    await completeOnboarding(server.trim(), token.trim() || undefined);
    router.replace("/");
  };

  const field = [styles.field, { backgroundColor: c.sf0, color: c.t1 }];

  return (
    <VoidStage>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.fill}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.column}>
            <Image source={APP_ICON} style={styles.icon} />

            <View style={styles.head}>
              <Display size={type.displayMD}>umbra</Display>
              <Mono size={type.monoSM} color={c.t3} style={styles.center}>
                the designer&apos;s ghost, in your pocket
              </Mono>
            </View>

            <View style={[styles.card, { backgroundColor: c.sf }]}>
              <View style={styles.group}>
                <MonoLabel>server</MonoLabel>
                <TextInput
                  style={field}
                  value={server}
                  onChangeText={setServer}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                  placeholder="http://192.168.1.10:18000"
                  placeholderTextColor={c.t3}
                />
              </View>

              <View style={styles.group}>
                <MonoLabel>agent token</MonoLabel>
                <TextInput
                  style={field}
                  value={token}
                  onChangeText={setToken}
                  autoCapitalize="none"
                  autoCorrect={false}
                  secureTextEntry
                  placeholder="gk_"
                  placeholderTextColor={c.t3}
                />
              </View>

              <View style={styles.consent}>
                <View style={[styles.dot, { backgroundColor: c.success }]} />
                <Body size={11.5} color={c.t3} style={styles.consentText}>
                  capture runs on the studio mac, never here. this app only reads the collector&apos;s status.
                </Body>
              </View>
            </View>

            <PressScale onPress={enter} style={[styles.cta, { backgroundColor: c.accent }]}>
              <Body size={type.bodyMD} weight="600" color={c.bg0}>
                enter the studio
              </Body>
            </PressScale>

            <Mono size={type.monoXS} color={c.t4} style={styles.center}>
              leave the token blank to use this build&apos;s own
            </Mono>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </VoidStage>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  column: { width: "100%", maxWidth: 400, gap: 20, alignItems: "center" },
  icon: {
    width: 76,
    height: 76,
    borderRadius: 19,
    shadowColor: "#000",
    shadowOpacity: 0.7,
    shadowRadius: 40,
    shadowOffset: { width: 0, height: 24 },
    elevation: 16,
  },
  head: { alignItems: "center", gap: 6 },
  center: { textAlign: "center" },
  card: { width: "100%", borderRadius: radii.deck, padding: 18, gap: 14 },
  group: { gap: 6 },
  field: {
    height: 42,
    borderRadius: radii.control,
    paddingHorizontal: 13,
    fontFamily: type.mono.family,
    fontSize: type.monoMD,
  },
  consent: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  dot: { width: 6, height: 6, borderRadius: 3, marginTop: 4 },
  consentText: { flex: 1, lineHeight: 11.5 * 1.55 },
  cta: {
    width: "100%",
    height: 46,
    borderRadius: radii.chip,
    alignItems: "center",
    justifyContent: "center",
  },
});
