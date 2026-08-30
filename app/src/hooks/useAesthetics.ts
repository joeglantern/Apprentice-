import { useQuery } from "@tanstack/react-query";

import { listAesthetics } from "@/lib/api";

export function useAesthetics() {
  return useQuery({
    queryKey: ["aesthetics"],
    queryFn: listAesthetics,
    staleTime: 60_000,
  });
}
