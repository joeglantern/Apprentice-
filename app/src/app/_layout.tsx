import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { StyleSheet, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AppShell } from "@/components/nav/AppShell";
import { Grain } from "@/components/ui/Grain";
import { ToastProvider } from "@/components/ui/Toast";
import { SessionProvider, useSession } from "@/state/session";
import { ThemeProvider, useTheme } from "@/theme/theme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Generated work is immutable once finished, and this is a studio tool on a
      // phone over a home network - holding results for a day costs nothing and
      // stops every screen change from refetching what it already had.
      gcTime: 24 * 60 * 60 * 1000,
      retry: 1,
    },
  },
});

export default function RootLayout() {
  // Kept at the top level of the root layout on purpose: Expo's static web
  // optimisation only picks fonts up when useFonts runs synchronously here, not
  // from inside an effect or a lazy boundary.
  //
  // Two naming sets, one set of files. The design system asks for SpaceGrotesk /
  // JetBrainsMono; the backend's layout.py names faces the way a designer would
  // ("Space Grotesk", "Bebas Neue"), and CanvasPreview renders SVG text with
  // whatever family the plan asked for - so both spellings have to resolve.
  const [loaded] = useFonts({
    Inter: require("../../assets/fonts/Inter[opsz,wght].ttf"),
    SpaceGrotesk: require("../../assets/fonts/SpaceGrotesk[wght].ttf"),
    JetBrainsMono: require("../../assets/fonts/JetBrainsMono.ttf"),
    "Space Grotesk": require("../../assets/fonts/SpaceGrotesk[wght].ttf"),
    "Bebas Neue": require("../../assets/fonts/BebasNeue-Regular.ttf"),
    "Playfair Display": require("../../assets/fonts/PlayfairDisplay[wght].ttf"),
  });

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <SessionProvider>
            <ToastProvider>
              <Shell fontsLoaded={loaded} />
            </ToastProvider>
          </SessionProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

function Shell({ fontsLoaded }: { fontsLoaded: boolean }) {
  const { c } = useTheme();
  const { authed, onboarded, ready } = useSession();

  // Hold on the void rather than flashing a system-font frame, or showing
  // onboarding to someone who finished it three launches ago.
  if (!fontsLoaded || !ready) return <View style={[styles.root, { backgroundColor: c.bg0 }]} />;

  return (
    <View style={[styles.root, { backgroundColor: c.bg0 }]}>
      <StatusBar style="light" />
      <AppShell>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: c.bg0 },
            // The chrome is persistent, so a slide between destinations would be
            // the content sliding under a bar that never moves.
            animation: "none",
          }}
        >
          <Stack.Protected guard={!authed}>
            <Stack.Screen name="auth" />
          </Stack.Protected>

          <Stack.Protected guard={authed && !onboarded}>
            <Stack.Screen name="onboarding" />
          </Stack.Protected>

          <Stack.Protected guard={authed && onboarded}>
            <Stack.Screen name="index" />
            <Stack.Screen name="create" />
            <Stack.Screen name="chat" />
            <Stack.Screen name="kits" />
            <Stack.Screen name="jobs" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="canvas" />
          </Stack.Protected>
        </Stack>
      </AppShell>
      <Grain />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
