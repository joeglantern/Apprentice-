import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

interface Props {
  onSubmit: (prompt: string) => void;
  busy?: boolean;
}

export function PromptInput({ onSubmit, busy }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const trimmed = text.trim();
    if (trimmed.length < 3 || busy) return;
    onSubmit(trimmed);
  };

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        placeholder="Poster for a summer jazz festival, Friday night, downtown park"
        placeholderTextColor="#8A8F98"
        value={text}
        onChangeText={setText}
        multiline
        editable={!busy}
      />
      <Pressable
        style={[styles.button, (busy || text.trim().length < 3) && styles.buttonDisabled]}
        onPress={submit}
        disabled={busy || text.trim().length < 3}
      >
        {busy ? (
          <ActivityIndicator color="#0B0B0F" />
        ) : (
          <Text style={styles.buttonText}>Generate</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 12 },
  input: {
    minHeight: 96,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#2A2D34",
    backgroundColor: "#15161B",
    color: "#F4F5F7",
    padding: 14,
    fontSize: 16,
    textAlignVertical: "top",
  },
  button: {
    backgroundColor: "#F4F5F7",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonDisabled: { opacity: 0.4 },
  buttonText: { color: "#0B0B0F", fontSize: 16, fontWeight: "600" },
});
