import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";

import { ApiError, createThread, getThread } from "@/lib/api";
import type { ChatThread } from "@/lib/types";
import { useSession } from "@/state/session";

/** The session create and chat are both working in.
 *
 * Threads are created lazily, on the first thing you actually send. They used to be
 * created on mount, which meant every visit to chat opened a new empty conversation
 * and orphaned the last one; with navigation no longer remounting screens that would
 * be rarer, but lazy creation removes the possibility rather than the frequency, and
 * it means an empty session cannot exist to clutter the session list.
 *
 * The id is persisted, so closing the app and coming back continues the same
 * conversation instead of starting over. */
export function useThread(seedJobId?: string | null) {
  const qc = useQueryClient();
  const { threadId, setThreadId, setActiveJobId } = useSession();
  // Two sends landing together must not create two threads.
  const creating = useRef<Promise<string> | null>(null);

  const thread = useQuery({
    queryKey: ["thread", threadId],
    queryFn: () => getThread(threadId as string),
    enabled: !!threadId,
    // The landed lines are settled server-side when the thread is read, so a poll
    // while a render is in flight is what makes them appear. Off once nothing is
    // pending, so an idle screen is not talking to the server.
    refetchInterval: (q) =>
      (q.state.data as ChatThread | undefined)?.messages.some((m) => m.job_id && !m.landed)
        ? 4000
        : false,
    // A session that is gone is gone. Retrying a 404 just costs a second request
    // before the effect below forgets it.
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });

  // A resumed session can be missing: deleted elsewhere, or the app now points at a
  // different server or token. Forget it rather than showing an error forever.
  const error = thread.error;
  useEffect(() => {
    if (error instanceof ApiError && error.status === 404) setThreadId(null);
  }, [error, setThreadId]);

  // The thread owns which piece is open; the rest of the app reads it from session.
  const open = thread.data?.active_job_id ?? null;
  useEffect(() => {
    if (open) setActiveJobId(open);
  }, [open, setActiveJobId]);

  const ensureThread = useCallback(async (): Promise<string> => {
    if (threadId) return threadId;
    if (creating.current) return creating.current;
    const pending = createThread(seedJobId ?? undefined)
      .then((t) => {
        qc.setQueryData(["thread", t.thread_id], t);
        setThreadId(t.thread_id);
        return t.thread_id;
      })
      .finally(() => {
        creating.current = null;
      });
    creating.current = pending;
    return pending;
  }, [threadId, seedJobId, qc, setThreadId]);

  return {
    threadId,
    thread: thread.data,
    messages: thread.data?.messages ?? [],
    activeJobId: open ?? seedJobId ?? null,
    ensureThread,
    loading: thread.isLoading,
  };
}
