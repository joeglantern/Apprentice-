import { useMutation } from "@tanstack/react-query";

import { generate } from "@/lib/api";

export function useGenerate() {
  return useMutation({
    mutationFn: ({
      prompt,
      aestheticVersion,
    }: {
      prompt: string;
      aestheticVersion: string;
    }) => generate(prompt, aestheticVersion),
  });
}
