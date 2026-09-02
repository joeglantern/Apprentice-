import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, generate, generateInThread } from "@/lib/api";
import type { BrandKit, ChatThread, JobKind } from "@/lib/types";
import { useSession } from "@/state/session";

import { useThread } from "./useThread";

interface Vars {
  prompt: string;
  aestheticVersion: string;
  kind: JobKind;
  size: [number, number];
  brand?: BrandKit;
}

/** Generate from the create deck, recorded as a turn in the current session.
 *
 * Goes to /chat/{id}/generate rather than /chat/{id}/turn: a turn asks the model what
 * the message meant and can decide it was a question, which is right for chat and
 * wrong for a button labelled generate. It also carries the deck's brand kit and
 * size, which a turn has nowhere to put.
 *
 * The session is a record of the work, not a precondition for it. If the session
 * cannot be opened or has gone missing, this falls back to plain /generate: the piece
 * is still made, it is simply not part of a conversation. */
export function useSessionGenerate() {
  const qc = useQueryClient();
  const { ensureThread } = useThread();
  const { setActiveJobId, setThreadId } = useSession();

  return useMutation({
    mutationFn: async (vars: Vars): Promise<{ jobId: string; thread: ChatThread | null }> => {
      const [width, height] = vars.size;
      const plain = async () => {
        const accepted = await generate(
          vars.prompt,
          vars.aestheticVersion,
          vars.kind,
          width,
          height,
          vars.brand,
        );
        return { jobId: accepted.job_id, thread: null };
      };

      let threadId: string;
      try {
        threadId = await ensureThread();
      } catch {
        return plain();
      }

      try {
        const thread = await generateInThread(threadId, {
          prompt: vars.prompt,
          aestheticVersion: vars.aestheticVersion,
          kind: vars.kind,
          width,
          height,
          brand: vars.brand,
        });
        return { jobId: thread.active_job_id as string, thread };
      } catch (err) {
        // Only a session that is gone falls back. A rejected aesthetic or a session
        // at its render cap is about the request, and the person should hear it.
        if (err instanceof ApiError && err.status === 404) {
          setThreadId(null);
          return plain();
        }
        throw err;
      }
    },

    onSuccess: ({ jobId, thread }) => {
      setActiveJobId(jobId);
      if (thread) qc.setQueryData(["thread", thread.thread_id], thread);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["threads"] });
    },
  });
}
