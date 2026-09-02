/** Thin fetch client. No React, no state - hooks/ wraps this for components. */

import Constants from "expo-constants";
import { Platform } from "react-native";

import type {
  Aesthetic,
  BrandKit,
  ChatThread,
  GenerateAccepted,
  Job,
  JobKind,
  JobSummary,
  QuickAction,
} from "./types";

/** On a phone, "localhost" is the phone - not the machine running the tunnel, which
 * is where the API actually is. Expo tells the bundle which host served it, so a
 * loopback URL in the env is rewritten to that host and a device works with no
 * configuration. Only loopback is rewritten; a real hostname is left alone. */
function resolveEnvBaseUrl(): string | undefined {
  const raw = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (!raw || Platform.OS === "web") return raw;
  if (!/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(raw)) return raw;

  const hostUri =
    Constants.expoConfig?.hostUri ??
    (Constants.expoGoConfig as { debuggerHost?: string } | undefined)?.debuggerHost;
  const host = hostUri?.split("/")[0]?.split(":")[0];
  if (!host || host === "localhost" || host === "127.0.0.1") return raw;

  return raw.replace(/(localhost|127\.0\.0\.1)/, host);
}

const ENV_BASE_URL = resolveEnvBaseUrl();
const ENV_AGENT_TOKEN = process.env.EXPO_PUBLIC_AGENT_TOKEN;

if (!ENV_BASE_URL) {
  // Fails loudly at import time in dev rather than every call failing mysteriously later.
  console.warn(
    "EXPO_PUBLIC_API_BASE_URL is not set - requests to the backend will fail. See app/.env.example.",
  );
}

/** Set from the onboarding screen's saved values at launch. Without this the
 * onboarding form would collect a server and token and then quietly do nothing,
 * since the build-time env would still be what every request used. */
let override: { baseUrl?: string; token?: string } = {};

export function configureApi(baseUrl?: string, token?: string): void {
  override = { baseUrl: baseUrl || undefined, token: token || undefined };
}

/** What onboarding should prefill: the resolved address, not the raw env. Showing
 * the raw "localhost" on a phone would be wrong on screen and, once saved, would
 * override the device-host resolution with an address that points at the phone. */
export function defaultBaseUrl(): string {
  return base() ?? "";
}

function base(): string | undefined {
  return override.baseUrl ?? ENV_BASE_URL;
}

function token(): string | undefined {
  return override.token ?? ENV_AGENT_TOKEN;
}

function headers(): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
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
  const res = await fetch(`${base()}/generate`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ prompt, aesthetic_version: aestheticVersion, kind, width, height, brand: brand ?? null }),
  });
  return unwrap<GenerateAccepted>(res);
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${base()}/generate/${jobId}`, { headers: headers() });
  return unwrap<Job>(res);
}

export async function listJobs(limit = 50): Promise<JobSummary[]> {
  const res = await fetch(`${base()}/generate?limit=${limit}`, { headers: headers() });
  return unwrap<JobSummary[]>(res);
}

export async function listAesthetics(): Promise<Aesthetic[]> {
  const res = await fetch(`${base()}/aesthetics`, { headers: headers() });
  return unwrap<Aesthetic[]>(res);
}

/** Full, authenticated URL for a rendered layer. Never use the backend's own
 * raster_url field directly - it's a relative path with no auth, meant only as a
 * human-readable hint, not something a client can fetch as-is. The token travels as
 * a query param here because react-native-svg's Image href can't carry a header. */
export function rasterUrl(jobId: string, layerId: string): string {
  const url = `${base()}/generate/${jobId}/raster/${layerId}`;
  const t = token();
  return t ? `${url}?token=${encodeURIComponent(t)}` : url;
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
  const res = await fetch(`${base()}/generate/${jobId}/revise`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(changes),
  });
  return unwrap<GenerateAccepted>(res);
}

export function socketBaseUrl(): string {
  return base() ?? "";
}

export function authToken(): string | undefined {
  return token();
}

/** Start a thread, optionally about a piece that already exists. */
export async function createThread(jobId?: string): Promise<ChatThread> {
  const res = await fetch(`${base()}/chat`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(jobId ? { job_id: jobId } : {}),
  });
  return unwrap<ChatThread>(res);
}

export async function getThread(threadId: string): Promise<ChatThread> {
  const res = await fetch(`${base()}/chat/${threadId}`, { headers: headers() });
  return unwrap<ChatThread>(res);
}

/** Send a message. The server reads it, decides what it means, does the work, and
 * returns the whole thread - so the client never has to guess what a turn did. */
export async function takeTurn(
  threadId: string,
  message: string,
  context: {
    aestheticVersion: string;
    kind: JobKind;
    width: number;
    height: number;
    quick?: QuickAction;
  },
): Promise<ChatThread> {
  const res = await fetch(`${base()}/chat/${threadId}/turn`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      message,
      aesthetic_version: context.aestheticVersion,
      kind: context.kind,
      width: context.width,
      height: context.height,
      quick: context.quick ?? null,
    }),
  });
  return unwrap<ChatThread>(res);
}
