# 04 - Expo app implementation

## 1. Folder structure (Expo Router, SDK 51+)

```
app/
├── app.json
├── package.json
├── src/
│   ├── app/                     # Expo Router file-based routes
│   │   ├── _layout.tsx
│   │   ├── index.tsx            # Prompt input screen
│   │   ├── aesthetic.tsx        # Aesthetic selector
│   │   └── canvas.tsx           # Interactive preview
│   ├── components/
│   │   ├── PromptInput.tsx
│   │   ├── AestheticSelector.tsx
│   │   └── CanvasPreview.tsx
│   ├── hooks/
│   │   └── useGenerate.ts       # React Query hook -> backend inference API
│   └── lib/
│       └── api.ts               # fetch client, base URL from env
```

## 2. Setup for Web + Expo Go from day one

```bash
npx create-expo-app@latest app --template tabs
cd app
npx expo install expo-router nativewind react-native-svg
npx expo start           # scan QR into Expo Go, or press `w` for web
```

Keep everything inside the Expo Go / Expo Router "managed" surface - no
custom native modules - so you never need a dev client build to test on
either platform. If a later feature genuinely needs a native module, that's
the moment to evaluate `expo-dev-client`, not before.

## 3. Screen specs

**Prompt input** (`index.tsx`) - a single text field plus a "Generate" button.
Minimal by design; the aesthetic is supplied by the model, not by prompt
engineering the user has to do.

**Aesthetic selector** (`aesthetic.tsx`) - a horizontal list of checkpoint
versions (e.g. "Style LoRA v1", "Style LoRA v2") if you end up training more
than one, so the designer/collaborator can compare outputs across training
runs rather than always hitting the latest one blind.

**Canvas preview** (`canvas.tsx`) - renders the layout model's structured
JSON (doc 01 §3) as actual SVG/CSS layers, with the style LoRA's raster
output composited inside them, per the vector/raster split in doc 01 §5:

```tsx
// src/components/CanvasPreview.tsx
import Svg, { Rect, Image as SvgImage, Text as SvgText } from "react-native-svg";

type Layer = {
  layer_id: string;
  type: "text" | "shape" | "image";
  bbox: { x: number; y: number; width: number; height: number };
  color?: { hex: string };
  raster_url?: string; // present when the style model generated fill content
};

export function CanvasPreview({ layers, canvasWidth, canvasHeight }: {
  layers: Layer[];
  canvasWidth: number;
  canvasHeight: number;
}) {
  return (
    <Svg width="100%" viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
      {layers.map((layer) => {
        if (layer.type === "image" && layer.raster_url) {
          return (
            <SvgImage
              key={layer.layer_id}
              href={{ uri: layer.raster_url }}
              x={layer.bbox.x} y={layer.bbox.y}
              width={layer.bbox.width} height={layer.bbox.height}
            />
          );
        }
        if (layer.type === "shape") {
          return (
            <Rect
              key={layer.layer_id}
              x={layer.bbox.x} y={layer.bbox.y}
              width={layer.bbox.width} height={layer.bbox.height}
              fill={layer.color?.hex ?? "#CCCCCC"}
            />
          );
        }
        return null; // text layers: extend with SvgText + typography from doc 01 §3
      })}
    </Svg>
  );
}
```

## 4. API integration

```typescript
// src/lib/api.ts
const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL!;

export async function generate(prompt: string, aestheticVersion: string) {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, aesthetic_version: aestheticVersion }),
  });
  if (!res.ok) throw new Error(`Generate failed: ${res.status}`);
  return res.json(); // { layers: Layer[], canvas_width, canvas_height }
}
```

```typescript
// src/hooks/useGenerate.ts
import { useMutation } from "@tanstack/react-query";
import { generate } from "../lib/api";

export function useGenerate() {
  return useMutation({
    mutationFn: ({ prompt, aestheticVersion }: { prompt: string; aestheticVersion: string }) =>
      generate(prompt, aestheticVersion),
  });
}
```

## 5. Live progress during generation

`generate()` above kicks off a job; the actual progress arrives over
Socket.IO from the server side described in doc 02 §5. `socket.io-client`
works the same way in Expo Go and on web - no extra setup needed:

```bash
npx expo install socket.io-client
```

```typescript
// src/hooks/useGenerationProgress.ts
import { useEffect, useState } from "react";
import { io, Socket } from "socket.io-client";

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL!;

export function useGenerationProgress(jobId: string | null) {
  const [progress, setProgress] = useState<{ step: number; total: number } | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const socket: Socket = io(BASE_URL, { transports: ["websocket"] });
    socket.on("connect", () => socket.emit("join", { room: jobId }));
    socket.on("progress", (data) => setProgress(data));
    // Reconnects automatically if the app backgrounds mid-generation and
    // resumes - this is the main reason to use Socket.IO here over a plain
    // WebSocket (doc 01 §6).
    return () => {
      socket.disconnect();
    };
  }, [jobId]);

  return progress;
}
```

Wire it into the prompt screen alongside `useGenerate` - kick off the job,
take the `job_id` from its response, and pass that into
`useGenerationProgress` to drive a progress bar while `CanvasPreview` waits
for the final layers.

`EXPO_PUBLIC_API_BASE_URL` points at whichever host ends up serving inference
per the trade-off in doc 01 §5 - keep it in `.env`, never hardcoded, so
switching between "VPS GPU tier", "Legion tunneled", or "burst GPU rental"
is a config change, not a code change.
