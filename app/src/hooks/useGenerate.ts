import { useMutation } from "@tanstack/react-query";

import { generate } from "@/lib/api";
import type { BrandKit, JobKind } from "@/lib/types";

/** Fallback canvas per kind, for callers that express no preference: posters and
 * photos are 4:5 portrait, a logo is square. The create deck passes an explicit
 * size instead, from its own chips. */
const SIZES: Record<JobKind, [number, number]> = {
  poster: [1080, 1350],
  image: [1080, 1350],
  logo: [1024, 1024],
};

export function useGenerate() {
  return useMutation({
    mutationFn: ({
      prompt,
      aestheticVersion,
      kind = "poster",
      size,
      brand,
    }: {
      prompt: string;
      aestheticVersion: string;
      kind?: JobKind;
      size?: [number, number];
      brand?: BrandKit;
    }) => generate(prompt, aestheticVersion, kind, ...(size ?? SIZES[kind]), brand),
  });
}
