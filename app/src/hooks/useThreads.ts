import { useQuery } from "@tanstack/react-query";

import { listThreads } from "@/lib/api";

/** The session list. Named after the piece each session is about, newest first. */
export function useThreads() {
  return useQuery({
    queryKey: ["threads"],
    queryFn: () => listThreads(),
    staleTime: 10_000,
  });
}
