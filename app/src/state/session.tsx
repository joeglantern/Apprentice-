/** Client-side session state: the selections that travel between screens, plus the
 * two flags that persist across launches.
 *
 * Server state (jobs, aesthetics, progress) is not here - that stays in the
 * existing react-query hooks. This holds only what the user has picked. */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { configureApi } from "@/lib/api";
import type { JobKind } from "@/lib/types";

export type SizeKey = "1:1" | "4:5" | "16:9" | "9:16";

/** The canvas each size maps to. Kept here rather than in the API layer so the
 * chips and the request cannot drift apart. */
export const SIZE_PX: Record<SizeKey, [number, number]> = {
  "1:1": [1024, 1024],
  "4:5": [1080, 1350],
  "16:9": [1344, 768],
  "9:16": [768, 1344],
};

interface Session {
  kind: JobKind;
  setKind: (k: JobKind) => void;
  size: SizeKey;
  setSize: (s: SizeKey) => void;
  aesthetic: string;
  setAesthetic: (a: string) => void;
  kitId: string;
  setKitId: (k: string) => void;
  /** The job the canvas and chat screens are looking at. */
  activeJobId: string | null;
  setActiveJobId: (id: string | null) => void;

  authed: boolean;
  onboarded: boolean;
  /** Null until the persisted flags have been read; screens wait rather than
   * flashing onboarding at someone who has already done it. */
  ready: boolean;
  completeAuth: () => Promise<void>;
  completeOnboarding: (apiBaseUrl?: string, token?: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const KEYS = { authed: "umbra-authed", onboarded: "umbra-onboarded", server: "umbra-server", token: "umbra-token" };

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [kind, setKind] = useState<JobKind>("poster");
  const [size, setSize] = useState<SizeKey>("4:5");
  // Baseline is the one aesthetic every server is guaranteed to have. Create
  // reconciles this against /aesthetics and moves it to a trained style when the
  // server reports one, so a stale selection can never be sent as a job.
  const [aesthetic, setAesthetic] = useState("baseline");
  const [kitId, setKitId] = useState("none");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const [authed, setAuthed] = useState(false);
  const [onboarded, setOnboarded] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [a, o, s, t] = await AsyncStorage.multiGet([
          KEYS.authed,
          KEYS.onboarded,
          KEYS.server,
          KEYS.token,
        ]);
        if (!alive) return;
        // Before anything can fetch: what onboarding saved outranks the build-time env.
        configureApi(s[1] ?? undefined, t[1] ?? undefined);
        setAuthed(a[1] === "1");
        setOnboarded(o[1] === "1");
      } catch {
        // Storage unavailable (private mode, first run on web): treat as a fresh
        // install rather than blocking the app.
      } finally {
        if (alive) setReady(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const completeAuth = useCallback(async () => {
    setAuthed(true);
    try {
      await AsyncStorage.setItem(KEYS.authed, "1");
    } catch {}
  }, []);

  const completeOnboarding = useCallback(async (apiBaseUrl?: string, token?: string) => {
    configureApi(apiBaseUrl, token);
    setOnboarded(true);
    try {
      const writes: [string, string][] = [[KEYS.onboarded, "1"]];
      if (apiBaseUrl) writes.push([KEYS.server, apiBaseUrl]);
      if (token) writes.push([KEYS.token, token]);
      await AsyncStorage.multiSet(writes);
    } catch {}
  }, []);

  const signOut = useCallback(async () => {
    // Clears the saved server and token too, not just the flags. A stale server
    // address is the most likely reason someone reaches for this, and leaving it
    // behind would send them back through onboarding to the same dead endpoint.
    configureApi(undefined, undefined);
    setAuthed(false);
    setOnboarded(false);
    setActiveJobId(null);
    try {
      await AsyncStorage.multiRemove([KEYS.authed, KEYS.onboarded, KEYS.server, KEYS.token]);
    } catch {}
  }, []);

  const value = useMemo<Session>(
    () => ({
      kind, setKind, size, setSize, aesthetic, setAesthetic, kitId, setKitId,
      activeJobId, setActiveJobId,
      authed, onboarded, ready, completeAuth, completeOnboarding, signOut,
    }),
    [kind, size, aesthetic, kitId, activeJobId, authed, onboarded, ready, completeAuth, completeOnboarding, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
