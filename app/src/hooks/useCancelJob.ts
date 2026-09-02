import { useMutation, useQueryClient } from "@tanstack/react-query";

import { cancelJob } from "@/lib/api";
import type { Job } from "@/lib/types";

/** Stop a generation. The job is terminal the moment the server answers, so the
 * screens waiting on it stop immediately even though the worker takes a second or
 * two to notice and put the GPU down. */
export function useCancelJob() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => cancelJob(jobId),
    onSuccess: (job: Job) => {
      qc.setQueryData(["job", job.job_id], job);
      void qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
