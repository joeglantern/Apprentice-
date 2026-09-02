/** Turns the worker's stage stream into the one number and one line the denoising
 * preview needs.
 *
 * The *line* is always the backend's own message, verbatim - it is written in plain
 * language ("thinking about the brief", "rendering 2/3") and rewriting it here would
 * only make the app say something less true than what is actually happening. The
 * percentage is ours, because the backend does not emit one. */

import { isTerminal, type Job, type JobStatus, type ProgressEvent } from "./types";

/** Where each stage sits on the bar. Render is a band, walked by step/total. */
const STAGE_PCT: Record<JobStatus, number> = {
  queued: 8,
  planning: 24,
  layout: 50,
  render: 66,
  done: 100,
  error: 100,
  cancelled: 100,
};

const RENDER_BAND = 28; // render runs 66 -> 94, leaving the last stretch for the finish

const FALLBACK_MESSAGE: Record<JobStatus, string> = {
  queued: "queued",
  planning: "thinking about the brief",
  layout: "composing the layout",
  render: "rendering",
  done: "done",
  error: "failed",
  cancelled: "stopped",
};

export interface Progress {
  pct: number;
  message: string;
  status: JobStatus;
}

export function readProgress(job: Job | undefined, event: ProgressEvent | null): Progress {
  // The socket is ahead of the poll, so it wins while both are talking about a job
  // still in flight. A terminal job status always wins - it is the settled truth.
  const status: JobStatus = isTerminal(job?.status)
    ? (job as Job).status
    : (event?.stage ?? job?.status ?? "queued");

  let pct = STAGE_PCT[status];
  if (status === "render" && event?.step && event?.total) {
    pct = STAGE_PCT.render + Math.round((event.step / event.total) * RENDER_BAND);
  }

  return {
    pct: Math.max(0, Math.min(100, pct)),
    message: event?.message?.trim() || FALLBACK_MESSAGE[status],
    status,
  };
}
