import { useMutation, useQueryClient } from "@tanstack/react-query";

import { reviseJob } from "@/lib/api";

/** Tweak a finished piece without replanning it: recompose, restyle the type, or
 * repaint the photo. Resolves to a new job, so the history list is refetched. */
export function useRevise() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      jobId,
      changes,
    }: {
      jobId: string;
      changes: {
        composition?: "anchor" | "centered" | "split";
        typeface?: "inter" | "bebas" | "playfair" | "grotesk";
        rerender_photo?: boolean;
      };
    }) => reviseJob(jobId, changes),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}
