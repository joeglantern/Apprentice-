import { useQuery } from "@tanstack/react-query";

import { socketBaseUrl } from "@/lib/api";

/** Is the configured server actually answering?
 *
 * Without this, a wrong address looks exactly like an empty studio: the lists come
 * back empty and every screen says "nothing yet". Settings shows the real answer,
 * and the lists use it to tell "no work" apart from "no server". */
export function useServerHealth() {
  const base = socketBaseUrl();

  return useQuery({
    queryKey: ["health", base],
    queryFn: async () => {
      if (!base) throw new Error("No server configured");
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 6000);
      try {
        const res = await fetch(`${base}/health`, { signal: controller.signal });
        if (!res.ok) throw new Error(`${res.status}`);
        return true;
      } finally {
        clearTimeout(timer);
      }
    },
    retry: 0,
    staleTime: 15_000,
    refetchInterval: (q) => (q.state.status === "error" ? 10_000 : 60_000),
  });
}
