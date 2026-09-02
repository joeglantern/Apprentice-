import { useQuery } from "@tanstack/react-query";

import { getJob } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

const TERMINAL: JobStatus[] = ["done", "error"];

/** Polls the job as a fallback/confirmation alongside the socket progress stream, and
 * is the source of truth for the final plan + rendered layers once status is terminal. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || TERMINAL.includes(status)) return false;
      return 2000;
    },
    // A done or failed job never changes again, so once it lands it is never
    // stale and never evicted for a day. Without this every return to explore
    // refetches the full layer JSON for every card on screen.
    staleTime: (query) =>
      TERMINAL.includes(query.state.data?.status as JobStatus) ? Infinity : 0,
    gcTime: 24 * 60 * 60 * 1000,
  });
}
