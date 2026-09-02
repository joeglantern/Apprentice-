/** Sign in / sign up.
 *
 * NOTE for whoever wires this up: the handoff's own README flags that auth extends
 * beyond the brief's single-studio-token model and asks the team to confirm whether
 * this is genuinely multi-user. The backend today authenticates one agent token, so
 * the OAuth rows and the email form are presentation only - they persist an authed
 * flag and move on. Point them at real providers before this ships. */

import { useRouter } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, TextInput, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { PressScale } from "@/components/ui/press";
import { Body, Display, Mono } from "@/components/ui/type";
import { UmbraMark } from "@/components/ui/marks";
import { VoidStage } from "@/components/ui/VoidStage";
import { noOutline } from "@/lib/styles";
import { type } from "@/lib/tokens";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

export default function AuthScreen() {
  const { c } = useTheme();
  const router = useRouter();
  const { completeAuth } = useSession();
  const [signup, setSignup] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = async () => {
    await completeAuth();
    router.replace("/onboarding");
  };

  const field = [styles.field, noOutline, { backgroundColor: c.sf, color: c.t1 }];

  return (
    <VoidStage>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.fill}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.column}>
            <View style={styles.head}>
              <UmbraMark size={44} color={c.t1} />
              <Display size={24} style={styles.title}>
                {signup ? "create your account" : "welcome back"}
              </Display>
              <Mono size={type.monoSM} color={c.t3}>
                the designer&apos;s ghost, in your pocket
              </Mono>
            </View>

            <View style={styles.stack}>
              <PressScale scale={0.98} onPress={submit} style={[styles.oauth, styles.oauthApple]}>
                <AppleMark />
                <Body size={type.bodySM} weight="500" color="#000000">
                  continue with apple
                </Body>
              </PressScale>
              <PressScale scale={0.98} onPress={submit} style={[styles.oauth, { backgroundColor: c.sf }]}>
                <GoogleMark />
                <Body size={type.bodySM} weight="500">
                  continue with google
                </Body>
              </PressScale>
            </View>

            <View style={styles.divider}>
              <View style={[styles.rule, { backgroundColor: c.ln }]} />
              <Mono size={type.monoXS} color={c.t4}>
                or email
              </Mono>
              <View style={[styles.rule, { backgroundColor: c.ln }]} />
            </View>

            <View style={styles.stack}>
              {signup ? (
                <TextInput
                  style={field}
                  placeholder="name"
                  placeholderTextColor={c.t3}
                  value={name}
                  onChangeText={setName}
                  autoComplete="name"
                />
              ) : null}
              <TextInput
                style={field}
                placeholder="email"
                placeholderTextColor={c.t3}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
              />
              <TextInput
                style={field}
                placeholder="password"
                placeholderTextColor={c.t3}
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoComplete={signup ? "new-password" : "current-password"}
              />
            </View>

            <PressScale onPress={submit} style={[styles.cta, { backgroundColor: c.accent }]}>
              <Body size={type.bodyMD} weight="600" color={c.bg0}>
                {signup ? "create account" : "sign in"}
              </Body>
            </PressScale>

            <PressScale scale={0.99} onPress={() => setSignup((s) => !s)} style={styles.toggle}>
              <Body size={12.5} color={c.t3}>
                {signup ? "already have an account? sign in" : "new here? create an account"}
              </Body>
            </PressScale>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </VoidStage>
  );
}

function AppleMark() {
  return (
    <Svg width={16} height={16} viewBox="0 0 384 512">
      <Path
        fill="#000000"
        d="M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1-2 49.9-15.2 69.5-34.3z"
      />
    </Svg>
  );
}

function GoogleMark() {
  return (
    <Svg width={16} height={16} viewBox="0 0 48 48">
      <Path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-3.1-.4-4.6H24v9.1h11.9c-.5 2.8-2.1 5.1-4.4 6.7v5.6h7.1c4.2-3.8 6.5-9.5 6.5-16.8z" />
      <Path fill="#34A853" d="M24 46c5.9 0 10.9-2 14.5-5.3l-7.1-5.6c-2 1.3-4.5 2.1-7.4 2.1-5.7 0-10.5-3.8-12.2-9h-7.3v5.7C7.9 40.9 15.3 46 24 46z" />
      <Path fill="#FBBC05" d="M11.8 28.2c-.4-1.3-.7-2.7-.7-4.2s.3-2.9.7-4.2v-5.7H4.5C3 17 2.1 20.4 2.1 24s.9 7 2.4 9.9z" />
      <Path fill="#EA4335" d="M24 10.7c3.2 0 6.1 1.1 8.4 3.2l6.3-6.3C34.9 4.1 29.9 2 24 2 15.3 2 7.9 7.1 4.5 14.1l7.3 5.7c1.7-5.2 6.5-9.1 12.2-9.1z" />
    </Svg>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  column: { width: "100%", maxWidth: 380, gap: 18 },
  head: { alignItems: "center", gap: 10 },
  title: { letterSpacing: -0.48 },
  stack: { gap: 10 },
  oauth: {
    height: 46,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  oauthApple: { backgroundColor: "#FFFFFF" },
  divider: { flexDirection: "row", alignItems: "center", gap: 10 },
  rule: { flex: 1, height: 1 },
  field: {
    height: 46,
    borderRadius: 12,
    paddingHorizontal: 14,
    fontSize: 14,
    fontFamily: type.body.family,
  },
  cta: { height: 48, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  toggle: { alignItems: "center", minHeight: 44, justifyContent: "center" },
});
