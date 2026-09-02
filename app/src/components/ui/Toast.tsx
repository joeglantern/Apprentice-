/** The one transient confirmation in the app: a mono pill, bottom centre, ~2.2s.
 * Exports and other fire-and-forget actions say so here rather than opening a
 * dialog that would have to be dismissed. */

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Animated, StyleSheet, View } from "react-native";

import { radii, type } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

import { Mono } from "./type";

const ToastContext = createContext<(message: string) => void>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((next: string) => {
    if (timer.current) clearTimeout(timer.current);
    setMessage(next);
    timer.current = setTimeout(() => setMessage(""), 2200);
  }, []);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  // A real View, not a fragment: the toast positions absolutely against it.
  return (
    <ToastContext.Provider value={show}>
      <View style={styles.root}>
        {children}
        {message ? <Toast message={message} /> : null}
      </View>
    </ToastContext.Provider>
  );
}

function Toast({ message }: { message: string }) {
  const { c, isDesktop } = useTheme();
  const [enter] = useState(() => new Animated.Value(0));

  useEffect(() => {
    enter.setValue(0);
    Animated.timing(enter, { toValue: 1, duration: 200, useNativeDriver: true }).start();
  }, [message, enter]);

  return (
    <View pointerEvents="none" style={[styles.host, { bottom: isDesktop ? 32 : 92 }]}>
      <Animated.View
        style={[
          styles.pill,
          {
            backgroundColor: c.raise2,
            opacity: enter,
            transform: [{ translateY: enter.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }],
          },
        ]}
      >
        <Mono size={type.monoSM} color={c.t1}>
          {message}
        </Mono>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  host: { position: "absolute", left: 0, right: 0, alignItems: "center", zIndex: 300 },
  pill: {
    borderRadius: radii.chip,
    paddingHorizontal: 18,
    paddingVertical: 9,
    shadowColor: "#000",
    shadowOpacity: 0.6,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 16 },
    elevation: 12,
  },
});
