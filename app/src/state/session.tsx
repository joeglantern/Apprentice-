/** Client-side session state: the selections that travel between screens, the
 * session being worked in, and the few preferences that outlive a launch.
 *
 * Server state (jobs, threads, aesthetics, progress) is not here - that stays in the
 * react-query hooks. This holds only what the user has chosen. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { configureApi } from "@/lib/api";
import { KEYS, readMany, remove, write } from "@/lib/storage";
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

  /** The conversation create and chat are both working in. Persisted, so closing
   * the app and coming back continues where you were instead of starting over. */
  threadId: string | null;
  setThreadId: (id: string | null) => void;
  /** Put down the current session. The next send or generate starts a new one
   * lazily, so an empty session can never exist. */
  newSession: () => void;

  /** null means "no stated preference", which the rail reads as "decide from the
   * window width". Only an explicit toggle writes it. */
  railExpanded: boolean | null;
  setRailExpanded: (open: boolean) => void;

  authed: boolean;
  onboarded: boolean;
  /** False until the persisted values have been read; the app waits rather than
   * flashing onboarding at someone who finished it three launches ago. */
  ready: boolean;
  completeAuth: () => Promise<void>;
  completeOnboarding: (apiBaseUrl?: string, token?: string) => Promise<void>;
  signOut: () => Promise<void>;
}

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
  const [threadId, setThread] = useState<string | null>(null);
  const [railExpanded, setRail] = useState<boolean | null>(null);

  const [authed, setAuthed] = useState(false);
  const [onboarded, setOnboarded] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const v = await readMany([
        KEYS.authed,
        KEYS.onboarded,
        KEYS.server,
        KEYS.token,
        KEYS.thread,
        KEYS.rail,
      ]);
      if (!alive) return;
      // Before anything can fetch: what onboarding saved outranks the build-time env.
      configureApi(v[KEYS.server] ?? undefined, v[KEYS.token] ?? undefined);
      setAuthed(v[KEYS.authed] === "1");
      setOnboarded(v[KEYS.onboarded] === "1");
      setThread(v[KEYS.thread]);
      setRail(v[KEYS.rail] === null ? null : v[KEYS.rail] === "expanded");
      setReady(true);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const setThreadId = useCallback((id: string | null) => {
    setThread(id);
    void write(KEYS.thread, id);
  }, []);

  const newSession = useCallback(() => {
    setThreadId(null);
    setActiveJobId(null);
  }, [setThreadId]);

  const setRailExpanded = useCallback((open: boolean) => {
    setRail(open);
    void write(KEYS.rail, open ? "expanded" : "collapsed");
  }, []);

  const completeAuth = useCallback(async () => {
    setAuthed(true);
    await write(KEYS.authed, "1");
  }, []);

  const completeOnboarding = useCallback(async (apiBaseUrl?: string, token?: string) => {
    configureApi(apiBaseUrl, token);
    setOnboarded(true);
    await write(KEYS.onboarded, "1");
    if (apiBaseUrl) await write(KEYS.server, apiBaseUrl);
    if (token) await write(KEYS.token, token);
  }, []);

  const signOut = useCallback(async () => {
    // Clears the saved server and token too, not just the flags. A stale server
    // address is the most likely reason someone reaches for this, and leaving it
    // behind would send them back through onboarding to the same dead endpoint.
    configureApi(undefined, undefined);
    setAuthed(false);
    setOnboarded(false);
    setActiveJobId(null);
    setThread(null);
    await remove([KEYS.authed, KEYS.onboarded, KEYS.server, KEYS.token, KEYS.thread]);
  }, []);

  const value = useMemo<Session>(
    () => ({
      kind, setKind, size, setSize, aesthetic, setAesthetic, kitId, setKitId,
      activeJobId, setActiveJobId,
      threadId, setThreadId, newSession,
      railExpanded, setRailExpanded,
      authed, onboarded, ready, completeAuth, completeOnboarding, signOut,
    }),
    [
      kind, size, aesthetic, kitId, activeJobId, threadId, setThreadId, newSession,
      railExpanded, setRailExpanded, authed, onboarded, ready,
      completeAuth, completeOnboarding, signOut,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
