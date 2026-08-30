import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { StyleSheet, View } from "react-native";

const queryClient = new QueryClient();

export default function RootLayout() {
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
          <Stack.Screen name="canvas" options={{ title: "Preview" }} />
        </Stack>
      </View>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0B0B0F" },
});
