import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { takeTurn } from "@/lib/api";
import type { ChatMessage, JobKind, QuickAction } from "@/lib/types";

import { useThread } from "./useThread";

/** The thread lives on the server, not in component state.
 *
 * It used to be a useState array, which meant a reload lost the conversation while
 * the jobs it produced survived - two halves of the same history disagreeing. It also
 * meant the assistant's lines were written by the client, which is why they could
 * only ever be canned. Now a turn is a request: the server reads the message, decides
 * what it means, does the work, and returns the thread as it now stands. */
export function useChat(seedJobId?: string | null) {
  const qc = useQueryClient();
  const session = useThread(seedJobId);

  /** The message being sent, held here rather than written into the query cache.
   *
   * The obvious optimistic-update shape (onMutate plus setQueryData) is wrong here:
   * the thread polls every four seconds while a render is unlanded, and a turn can
   * take far longer than that, so a poll arriving mid-flight would overwrite the
   * cache and the bubble would vanish and come back. Kept beside the server data it
   * is immune to refetches, and rolling it back is dropping a variable. */
  const [pending, setPending] = useState<string | null>(null);

  const send = useMutation({
    mutationFn: async (vars: {
      message: string;
      aestheticVersion: string;
      kind: JobKind;
      width: number;
      height: number;
      quick?: QuickAction;
    }) => {
      const threadId = await session.ensureThread();
      return takeTurn(threadId, vars.message, {
        aestheticVersion: vars.aestheticVersion,
        kind: vars.kind,
        width: vars.width,
        height: vars.height,
        quick: vars.quick,
      });
    },
    onMutate: (vars) => setPending(vars.message),
    onSettled: () => setPending(null),
    onSuccess: (updated) => {
      qc.setQueryData(["thread", updated.thread_id], updated);
      // A turn can start a render, so both the history list and the session list
      // (which is named after the open piece) are stale.
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["threads"] });
    },
  });

  /** Server messages, with the one in flight on the end so it is on screen the
   * instant it is sent. Its id is stable so the entrance animation does not replay. */
  const messages: ChatMessage[] = pending
    ? [
        ...session.messages,
        {
          message_id: "pending",
          role: "user",
          text: pending,
          action: null,
          job_id: null,
          landed: null,
          created_at: new Date().toISOString(),
        },
      ]
    : session.messages;

  return {
    threadId: session.threadId,
    thread: session.thread,
    messages,
    /** The id of the message still in flight, so the view can dim it. */
    pendingId: pending ? "pending" : null,
    activeJobId: session.activeJobId,
    sending: send.isPending,
    error: send.error as Error | undefined,
    send: send.mutate,
  };
}
