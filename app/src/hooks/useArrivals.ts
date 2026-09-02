import { useEffect, useRef, useState } from "react";

import { motion } from "@/lib/tokens";

/** Which of these ids are new since the last render, so only those animate in.
 *
 * The first run deliberately marks nothing. Opening a thread with twenty messages
 * should show a thread, not play twenty fades at once; only what arrives while you
 * are watching is an arrival. */
export function useArrivals(ids: string[]): Set<string> {
  const seen = useRef<Set<string> | null>(null);
  const [arriving, setArriving] = useState<Set<string>>(() => new Set());

  const key = ids.join(",");
  useEffect(() => {
    if (seen.current === null) {
      seen.current = new Set(ids);
      return;
    }
    const fresh = ids.filter((id) => !seen.current!.has(id));
    seen.current = new Set(ids);
    if (fresh.length === 0) return;

    setArriving((prev) => new Set([...prev, ...fresh]));
    const timer = setTimeout(() => {
      setArriving((prev) => {
        const next = new Set(prev);
        for (const id of fresh) next.delete(id);
        return next;
      });
    }, motion.fadeUpMs + 60);
    return () => clearTimeout(timer);
    // key rather than ids: a new array with the same contents is not an arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return arriving;
}
