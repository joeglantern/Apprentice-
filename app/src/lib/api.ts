/** Thin fetch client. No React, no state - hooks/ wraps this for components. */

import type { Aesthetic, BrandKit, GenerateAccepted, Job, JobKind, JobSummary } from "./types";

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL;
const AGENT_TOKEN = process.env.EXPO_PUBLIC_AGENT_TOKEN;

if (!BASE_URL) {
  // Fails loudly at import time in dev rather than every call failing mysteriously later.
  console.warn(
    "EXPO_PUBLIC_API_BASE_URL is not set - requests to the backend will fail. See app/.env.example.",
  );
}

function headers(): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (AGENT_TOKEN) h["Authorization"] = `Bearer ${AGENT_TOKEN}`;
  return h;
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function generate(
  prompt: string,
  aestheticVersion: string,
  kind: JobKind = "poster",
  width = 1080,
  height = 1350,
  brand?: BrandKit,
): Promise<GenerateAccepted> {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ prompt, aesthetic_version: aestheticVersion, kind, width, height, brand: brand ?? null }),
  });
  return unwrap<GenerateAccepted>(res);
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE_URL}/generate/${jobId}`, { headers: headers() });
  return unwrap<Job>(res);
}

export async function listJobs(limit = 50): Promise<JobSummary[]> {
  const res = await fetch(`${BASE_URL}/generate?limit=${limit}`, { headers: headers() });
  return unwrap<JobSummary[]>(res);
}

export async function listAesthetics(): Promise<Aesthetic[]> {
  const res = await fetch(`${BASE_URL}/aesthetics`, { headers: headers() });
  return unwrap<Aesthetic[]>(res);
}

/** Full, authenticated URL for a rendered layer. Never use the backend's own
 * raster_url field directly - it's a relative path with no auth, meant only as a
 * human-readable hint, not something a client can fetch as-is. The token travels as
 * a query param here because react-native-svg's Image href can't carry a header. */
export function rasterUrl(jobId: string, layerId: string): string {
  const url = `${BASE_URL}/generate/${jobId}/raster/${layerId}`;
  return AGENT_TOKEN ? `${url}?token=${encodeURIComponent(AGENT_TOKEN)}` : url;
}

/** Tweak a finished poster without replanning; resolves to the new job. */
export async function reviseJob(
  jobId: string,
  changes: {
    composition?: "anchor" | "centered" | "split";
    typeface?: "inter" | "bebas" | "playfair" | "grotesk";
    rerender_photo?: boolean;
  },
): Promise<GenerateAccepted> {
  const res = await fetch(`${BASE_URL}/generate/${jobId}/revise`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(changes),
  });
  return unwrap<GenerateAccepted>(res);
}

export function socketBaseUrl(): string {
  return BASE_URL ?? "";
}

export function authToken(): string | undefined {
  return AGENT_TOKEN;
}
