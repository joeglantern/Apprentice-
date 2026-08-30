import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { StyleSheet, View } from "react-native";

const queryClient = new QueryClient();

export default function RootLayout() {
  // The bundled OFL faces layout.py can ask for by family name (backend
  // FONT_PAIRINGS). Rendering proceeds either way; SVG text falls back to the
  // system face until these resolve, then re-renders.
  useFonts({
    Inter: require("../../assets/fonts/Inter[opsz,wght].ttf"),
    "Bebas Neue": require("../../assets/fonts/BebasNeue-Regular.ttf"),
    "Playfair Display": require("../../assets/fonts/PlayfairDisplay[wght].ttf"),
    "Space Grotesk": require("../../assets/fonts/SpaceGrotesk[wght].ttf"),
  });

  return (
    <QueryClientProvider client={queryClient}>
      <View style={styles.root}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: "#0B0B0F" },
            headerTintColor: "#F4F5F7",
            contentStyle: { backgroundColor: "#0B0B0F" },
          }}
        >
          <Stack.Screen name="index" options={{ title: "Ghost Agent" }} />
          <Stack.Screen name="history" options={{ title: "History" }} />
          <Stack.Screen name="canvas" options={{ title: "Preview" }} />
        </Stack>
      </View>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0B0B0F" },
});
