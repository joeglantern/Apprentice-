# app

Expo Router app (Web + iOS + Android via Expo Go). Prompt in, live progress, the
composited result out. See `docs/04_EXPO_APP_IMPLEMENTATION.md` for the original spec
and `.claude/skills/expo-canvas-conventions/SKILL.md` for the conventions this follows.

Visual design (theme, icons, real polish) is being done separately via Claude Design -
what's here is the functional scaffold: real screens, real API calls, real state, plain
`StyleSheet` styling as a placeholder until that pass happens.

## Screens
- **`/` (index)** - aesthetic picker + prompt box. Submits, then pushes to `/canvas`.
- **`/canvas`** - live progress (Socket.IO) while a job runs, then the composited layers
  once it's done, plus the director's rationale.
- **`/history`** - the signed-in agent's own past generations, newest first, tap through
  to re-view any of them on `/canvas`.

## Setup
```bash
cp .env.example .env.local     # fill in EXPO_PUBLIC_API_BASE_URL and EXPO_PUBLIC_AGENT_TOKEN
npm install
npx expo start                 # press w for web, or scan the QR into Expo Go
```
`EXPO_PUBLIC_API_BASE_URL` needs a real path to the backend - the VPS through an SSH
tunnel while there's no hostname yet (`ssh -N -L 8000:127.0.0.1:8000 liban@<vps>`, then
`http://localhost:8000`), a real hostname later. `EXPO_PUBLIC_AGENT_TOKEN` is the `app`
agent's token from the VPS's `backend/.env` `AGENT_TOKENS` list.

## Structure
```
src/
├── app/            # Expo Router routes - thin, no fetch logic
├── components/     # PromptInput, AestheticSelector, CanvasPreview, ProgressBar
├── hooks/          # useGenerate, useJob, useJobHistory, useGenerationProgress, useAesthetics
└── lib/            # api.ts (fetch client), types.ts (mirrors the backend's doc 01 schema)
```

## Known gap
`CanvasPreview`'s rendered-image layers need the same bearer token as every other
backend route, but `react-native-svg`'s `Image` doesn't carry custom headers on its
`href`. Not solved yet - needs either a signed URL from the backend or a short-lived
query-param token on the raster route. Text and shape layers render fully today; image
layers will 401 until that's fixed.

## Verify before calling a change done
```bash
npx tsc --noEmit
npx expo lint
npx expo start   # confirm on web (w) - Expo Go needs a real device/simulator
```
