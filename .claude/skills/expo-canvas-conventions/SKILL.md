---
name: expo-canvas-conventions
description: Conventions for the Expo Router app's screens, hooks, and SVG canvas rendering. Use when writing or editing anything under app/.
---

# Expo app conventions (`app/`)

Spec: `docs/04_EXPO_APP_IMPLEMENTATION.md`. Rules from `CLAUDE.md`:
TypeScript **strict**, functional components only, no class components.

## Non-negotiable platform constraint
Everything must run in **Expo Go and on Web without a dev-client build**.
No custom native modules. Allowed: `expo-router`, `nativewind`,
`react-native-svg`, `@tanstack/react-query`, `socket.io-client`. If a
feature seems to need a native module, stop and raise it before adding
`expo-dev-client`.

## Structure
```
app/src/
├── app/            # Expo Router routes only - thin, compose components
│   ├── _layout.tsx # QueryClientProvider + Stack
│   ├── index.tsx   # prompt input
│   ├── aesthetic.tsx
│   └── canvas.tsx
├── components/     # PromptInput, AestheticSelector, CanvasPreview
├── hooks/          # useGenerate, useGenerationProgress, useAesthetics
└── lib/            # api.ts (fetch client), types.ts (Layer etc.)
```
Routes hold no fetch logic; hooks hold no JSX.

## API
- Base URL from `process.env.EXPO_PUBLIC_API_BASE_URL` - never hard-coded;
  switching VPS / Legion / burst GPU is a `.env` change.
- `lib/api.ts` exports typed functions; `useGenerate` wraps them in
  `useMutation`. Throw on `!res.ok` with the status in the message.
- Shared types (`Layer`, `GenerateResponse`) mirror the doc 01 §3 schema
  and live in `lib/types.ts`.

## Canvas (vector/raster compositing - doc 01 §5, doc 04 §3)
`CanvasPreview` renders the layout model's JSON as SVG in a single
`<Svg viewBox="0 0 W H" width="100%">`:
- Sort layers by `z_index` ascending before mapping.
- `shape` -> `<Rect>` filled with `color.hex` (fallback `#CCCCCC`), honour
  `color.opacity`.
- `image` with `raster_url` -> `<SvgImage href={{uri}}>` at the bbox - this is
  where the style LoRA's raster output is composited inside the vector
  structure.
- `text` -> `<SvgText>` using `typography` (family, size, weight,
  letter-spacing); fall back to a system font when the family isn't
  available on the device.
- Never use absolute pixel positioning outside the SVG; the viewBox is the
  coordinate system so the same JSON renders identically on web and phone.

## Progress
`useGenerationProgress(jobId)` opens `socket.io-client` with
`transports: ["websocket"]`, emits `join {room: jobId}` on connect, and
updates on `progress`. Disconnect in the effect cleanup. Rely on Socket.IO's
reconnection for backgrounded apps - don't reimplement it.

## Verification before "done"
`npx expo start` -> confirm on **both** web (`w`) and Expo Go (QR). Run
`npx tsc --noEmit` and `npx expo lint`.
