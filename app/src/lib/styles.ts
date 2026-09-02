import { Platform, type TextStyle } from "react-native";

/** Kills the browser's focus ring on text inputs.
 *
 * Chrome draws its own outline on a focused input, which lands on top of the
 * design's surfaces and looks like a rendering fault. `outlineStyle` is a
 * react-native-web style with no React Native equivalent, so it is not in TextStyle
 * and has to be cast; it is a no-op on native. */
export const noOutline = (
  Platform.OS === "web" ? ({ outlineStyle: "none", outlineWidth: 0 } as unknown as TextStyle) : {}
) as TextStyle;

/** True when a key press should send rather than insert a newline.
 *
 * Enter sends, shift+enter makes a new line - the create deck's documented
 * shortcut. A multiline TextInput never fires onSubmitEditing for Enter, so the
 * key has to be read directly. */
export function isSubmitKey(e: { nativeEvent: { key: string } }): boolean {
  const native = e.nativeEvent as { key: string; shiftKey?: boolean };
  return native.key === "Enter" && !native.shiftKey;
}
