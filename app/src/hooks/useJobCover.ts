import { useJob } from "./useJob";

import { rasterUrl } from "@/lib/api";
import type { JobKind } from "@/lib/types";

/** Aspect a card reserves before its render has arrived.
 *
 * The list endpoint returns summaries only (no result), which is deliberate on the
 * backend - plan and layers are large and a grid never reads them. So the grid is
 * laid out from the kind alone and each cover fills in afterwards; without this the
 * whole page would have to wait on every job detail before it could place anything. */
export function coverAspect(kind: JobKind): number {
  return kind === "logo" ? 1 : 1080 / 1350;
}

/** The finished artwork for a job, or null while it is still being fetched.
 *
 * One request per visible card. If the grid ever feels heavy over a slow link, the
 * fix is a cover field on JobSummary rather than caching harder here. */
export function useJobCover(jobId: string): string | null {
  const { data } = useJob(jobId);
  if (!data?.result) return null;

  const layer =
    data.result.layers.find((l) => l.type === "image" && l.raster_key) ??
    data.result.layers.find((l) => l.raster_key);

  return layer ? rasterUrl(jobId, layer.layer_id) : null;
}
