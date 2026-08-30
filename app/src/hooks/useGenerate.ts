import { useMutation } from "@tanstack/react-query";

import { generate } from "@/lib/api";
import type { BrandKit, JobKind } from "@/lib/types";

/** Canvas per kind: posters and photos are 4:5 portrait, a logo is square. */
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
      brand,
    }: {
      prompt: string;
      aestheticVersion: string;
      kind?: JobKind;
      brand?: BrandKit;
    }) => generate(prompt, aestheticVersion, kind, ...SIZES[kind], brand),
  });
}
