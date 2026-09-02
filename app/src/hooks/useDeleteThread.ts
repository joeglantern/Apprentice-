import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteThread } from "@/lib/api";
import type { ThreadSummary } from "@/lib/types";

/** Forget a session. The pieces it made stay in explore, which is why this is not
 * a destructive-sounding confirmation: the work is not going anywhere.
 *
 * The row leaves the list at once and comes back if the server refuses. */
export function useDeleteThread() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (threadId: string) => deleteThread(threadId),

    onMutate: async (threadId) => {
      await qc.cancelQueries({ queryKey: ["threads"] });
      const previous = qc.getQueryData<ThreadSummary[]>(["threads"]);
      qc.setQueryData<ThreadSummary[]>(["threads"], (old) =>
        (old ?? []).filter((t) => t.thread_id !== threadId),
      );
      return { previous };
    },

    onError: (_err, _id, context) => {
      if (context?.previous) qc.setQueryData(["threads"], context.previous);
    },

    onSettled: (_data, _err, threadId) => {
      qc.removeQueries({ queryKey: ["thread", threadId] });
      void qc.invalidateQueries({ queryKey: ["threads"] });
    },
  });
}
