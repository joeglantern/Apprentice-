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
  });
}
