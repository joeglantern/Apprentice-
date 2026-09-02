import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteJob } from "@/lib/api";
import type { JobSummary } from "@/lib/types";

/** Remove a generation. The row leaves the grid immediately and comes back if the
 * server refuses, so a delete feels instant without lying about having worked. */
export function useDeleteJob() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => deleteJob(jobId),

    onMutate: async (jobId) => {
      await qc.cancelQueries({ queryKey: ["jobs"] });
      const previous = qc.getQueryData<JobSummary[]>(["jobs"]);
      qc.setQueryData<JobSummary[]>(["jobs"], (old) =>
        (old ?? []).filter((j) => j.job_id !== jobId),
      );
      return { previous };
    },

    onError: (_err, _jobId, context) => {
      if (context?.previous) qc.setQueryData(["jobs"], context.previous);
    },

    onSettled: (_data, _err, jobId) => {
      qc.removeQueries({ queryKey: ["job", jobId] });
      void qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
