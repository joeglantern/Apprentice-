import { useEffect, useState } from "react";
import { io, type Socket } from "socket.io-client";

import { authToken, socketBaseUrl } from "@/lib/api";
import type { ProgressEvent } from "@/lib/types";

/** Live progress for one job, over the same Socket.IO room the worker emits into
 * (backend/app/worker.py). Reconnects automatically if the app backgrounds mid
 * generation - that's Socket.IO's job, not this hook's. */
export function useGenerationProgress(jobId: string | null) {
  const [progress, setProgress] = useState<ProgressEvent | null>(null);

  useEffect(() => {
    if (!jobId) return;
    // auth is checked server-side on connect (realtime.py) - joining a room the
    // token's agent doesn't own is refused there too, not just at the handshake.
    const socket: Socket = io(socketBaseUrl(), {
      transports: ["websocket"],
      auth: { token: authToken() },
    });
    socket.on("connect", () => socket.emit("join", { room: jobId }));
    socket.on("progress", (data: ProgressEvent) => {
      if (data.job_id === jobId) setProgress(data);
    });
    return () => {
      socket.disconnect();
      setProgress(null); // reset on cleanup (jobId changed or unmount), not synchronously in the body
    };
  }, [jobId]);

  return progress;
}
