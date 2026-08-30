/** Thin fetch client. No React, no state - hooks/ wraps this for components. */

import type { Aesthetic, GenerateAccepted, Job } from "./types";

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
  width = 1600,
  height = 900,
): Promise<GenerateAccepted> {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ prompt, aesthetic_version: aestheticVersion, width, height }),
  });
  return unwrap<GenerateAccepted>(res);
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE_URL}/generate/${jobId}`, { headers: headers() });
  return unwrap<Job>(res);
}

export async function listJobs(limit = 50): Promise<Job[]> {
  const res = await fetch(`${BASE_URL}/generate?limit=${limit}`, { headers: headers() });
  return unwrap<Job[]>(res);
}

export async function listAesthetics(): Promise<Aesthetic[]> {
  const res = await fetch(`${BASE_URL}/aesthetics`, { headers: headers() });
  return unwrap<Aesthetic[]>(res);
}

export function rasterUrl(jobId: string, layerId: string): string {
  return `${BASE_URL}/generate/${jobId}/raster/${layerId}`;
}

export function socketBaseUrl(): string {
  return BASE_URL ?? "";
}

export function authToken(): string | undefined {
  return AGENT_TOKEN;
}
