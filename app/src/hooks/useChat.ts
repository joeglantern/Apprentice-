import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { createThread, getThread, takeTurn } from "@/lib/api";
import type { ChatThread, JobKind, QuickAction } from "@/lib/types";

/** The thread lives on the server, not in component state.
 *
 * It used to be a useState array, which meant a reload lost the conversation while
 * the jobs it produced survived - two halves of the same history disagreeing. It also
 * meant the assistant's lines were written by the client, which is why they could
 * only ever be canned. Now a turn is a request: the server reads the message, decides
 * what it means, does the work, and returns the thread as it now stands.
 */
export function useChat(seedJobId?: string | null) {
  const qc = useQueryClient();
  const [threadId, setThreadId] = useState<string | null>(null);

  // One thread per visit to the screen, adopting whatever piece is open so the first
  // message can be about it. Creating it eagerly (rather than on first send) keeps
  // send a single request, which is the one the user is waiting on.
  useEffect(() => {
    if (threadId) return;
    let live = true;
    createThread(seedJobId ?? undefined)
      .then((t) => {
        if (!live) return;
        setThreadId(t.thread_id);
        qc.setQueryData(["thread", t.thread_id], t);
      })
      .catch(() => {
        /* surfaced by the send below, where there is somewhere to show it */
      });
    return () => {
      live = false;
    };
  }, [threadId, seedJobId, qc]);

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
  });

  const send = useMutation({
    mutationFn: (vars: {
      message: string;
      aestheticVersion: string;
      kind: JobKind;
      width: number;
      height: number;
      quick?: QuickAction;
    }) =>
      takeTurn(threadId as string, vars.message, {
        aestheticVersion: vars.aestheticVersion,
        kind: vars.kind,
        width: vars.width,
        height: vars.height,
        quick: vars.quick,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(["thread", updated.thread_id], updated);
      // A turn can start a render, so the history list is stale.
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  return {
    threadId,
    thread: thread.data,
    messages: thread.data?.messages ?? [],
    activeJobId: thread.data?.active_job_id ?? seedJobId ?? null,
    ready: !!threadId,
    sending: send.isPending,
    error: send.error as Error | undefined,
    send: send.mutate,
  };
}
