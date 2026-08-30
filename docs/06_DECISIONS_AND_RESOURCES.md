# 06 - Decisions log and external resources

Decisions made after the original 01-05 docs, with the operator, during
build. Later docs and code follow this file where it differs from 01-05.

## D1 - "Intelligent and thoughtful", not just imitative (2026-08-29)

The operator wants the generator to *think* about a brief, not only
reproduce the designer's habits. A fine-tuned 3B VLM cannot do that; it
pattern-matches. So generation becomes a **three-stage pipeline**:

| Stage | Component | Learns / provides | Runs on |
|---|---|---|---|
| 1. Creative director | Frontier LLM (Claude API, tool-use) | Reasons about the brief: message, audience, hierarchy, copy, mood, which elements exist and why. Emits a **design plan** (structured JSON: elements, roles, priorities, mood words, palette intent). Has the designer's style profile (§D3) in its context so its reasoning is grounded in *his* taste. | VPS (API call) |
| 2. Layout model | Qwen2.5-VL-3B QLoRA, LayoutPrompter-style text serialisation (§D2) | The designer's **composition habits** - converts the plan's elements into bboxes / typography / z-order the way he would place them. | Legion |
| 3. Style renderer | SDXL + style LoRA (IP-Adapter as day-one baseline, §D2) | The designer's **visual texture** for raster fills inside the vector structure. | Legion (burst GPU fallback) |

Stage 1 is what makes it thoughtful; stages 2-3 are what make it *his*.
Stage 1 also critiques: after 2-3 produce a candidate, the director can
score it against the plan and request a re-layout (bounded to 2 passes).

Consequences:
- `backend/` gains a `director` module (Claude API, tool-use with a
  `design_plan` schema) and `/generate` becomes a 3-step Celery job with
  Socket.IO progress per stage (`planning` -> `layout` -> `render` -> `done`).
- `ANTHROPIC_API_KEY` joins `backend/.env.example`.
- The app shows the director's plan (one paragraph of rationale + the
  element list) alongside the canvas, so the collaborator sees *why*.
- Cost is per-generation API spend, not GPU - fine at two-person scale.

## D2 - Repos and datasets adopted

| Resource | Used for | Phase |
|---|---|---|
| `kohya-ss/sd-scripts` | SDXL style-LoRA training. Replaces diffusers' `train_dreambooth_lora_sdxl.py` as the primary trainer - better tested at 8GB, memory flags built in. | 3 |
| `tencent-ailab/IP-Adapter` | **Day-one style baseline**: reference-image conditioning with no training, so the app renders in a recognisable style before the first LoRA exists. Stays as a fallback afterwards. | 3/4 |
| `microsoft/LayoutPrompter` (+ PosterLlama paper) | The **serialisation format** for layout training pairs: elements as text tokens (`<text x=120 y=80 w=640 h=96>` ...) rather than raw JSON regression. Far more sample-efficient, and lets the design plan from D1 be the model's input prompt. | 3 |
| CGL-Dataset, PKU-PosterLayout | Layout **pretraining** pass so the model isn't learning composition from ~40 of the designer's files. Rico / PubLayNet stay as sanity benchmarks. | 3 |
| `comfyanonymous/ComfyUI` | The **inference server on the Legion** (HTTP API, LoRA + IP-Adapter loading, queueing) instead of a hand-written diffusers server. Gateway on the VPS calls its `/prompt` API over the tunnel. | 2b/4 |
| `psd-tools` | PSD parsing (unchanged from doc 02). | 1 |

Not adopted: LayoutParser (benchmark only), Flux (still a stretch goal at
8GB), 7B VLMs (stretch).

## D3 - Style profile (new artefact)

A small, human-readable JSON the training pipeline derives from the curated
dataset (dominant palettes, typical type scales, margin ratios, alignment
habits, recurring layer roles) and that the director (D1) receives in its
system prompt. It is regenerated on each nightly curation and versioned
next to the checkpoints. It is also the first thing the designer can read
to see what the system believes about his work.

## D4 - Test hardware for the collector

The operator has a **2015 MacBook Pro (Intel)** for testing the collector
before it goes on the designer's M4. Constraints that follow:
- Max macOS is 12 Monterey -> Python 3.11 via Homebrew (`brew install
  python@3.11`), not the system Python. The launchd plist points at the
  Homebrew interpreter, not `/usr/bin/python3`.
- `rumps`, `watchdog`, `psd-tools` all run on Intel; no Apple-Silicon-only
  wheels are involved.
- Photoshop for the UXP panel needs v22+; if the 2015 machine can't run a
  UXP-capable Photoshop, the panel is tested on the M4 only and the
  menu-bar agent (which does not depend on the panel) is tested on the 2015.

## D5 - Hardware confirmation

Operator confirmed on 2026-08-29: Legion RTX 5060 mobile 8GB; Contabo VPS
CPU-only. Milestone plan M1-M5 (kickoff Phase 0 step 4) accepted, with
D1/D2 folded into M3-M5.

## D6 - VPS deployment (2026-08-30)

The Contabo box (Ubuntu 24.04, 12 cores, 47 GB RAM) is shared with other
projects. Host nginx owns ports 80 and 443 and the host runs its own
Postgres and Redis, so the Ghost Agent stack keeps everything inside its
own compose network and binds only the API to 127.0.0.1:8000, Flower to
127.0.0.1:5555 and MinIO to 127.0.0.1:9000 and 9001.

- Checkout: `~/ghost-agent` on the VPS, compose project name `ghostagent`,
  started with `docker compose -p ghostagent -f docker-compose.yml -f
  docker-compose.vps.yml up -d --build`.
- Object storage is a local MinIO (`docker-compose.vps.yml`) until Contabo
  S3 credentials exist. Switching later is an env change plus a one time
  copy of the bucket.
- Secrets live only in `~/ghost-agent/backend/.env` on the server
  (Postgres password, MinIO root, agent tokens for `mac-2015` and `mac-m4`).
- Until a hostname points at the box, the collector reaches the API through
  an SSH tunnel: `ssh -N -L 8000:127.0.0.1:8000 liban@<vps>` on the Mac and
  pair with `http://localhost:8000`. Once a hostname exists, the host nginx
  gets a server block proxying to 127.0.0.1:8000 with the WebSocket upgrade
  headers from `backend/nginx.conf`, and certbot issues the certificate.
- Tailscale is not installed yet. It is still the plan for the VPS to Legion
  link (training pull, inference gateway) and would also replace the SSH
  tunnel for the collector.

## D7 - Free director backend, no paid API required (2026-08-30)

The operator has no budget for the Claude API. The director (D1) already had a
heuristic fallback for when no model is configured; this adds a real, free
middle tier so the pipeline still reasons about a brief without a paid call.

Three backends now, tried in order, each a strict fallback of the one before:

1. **Claude API** - unchanged from D1. Best quality, costs money, entirely
   optional. Off unless `ANTHROPIC_API_KEY` is set.
2. **Local LLM (new, the recommended path at zero budget)** - a small
   open-weight instruct model (Qwen2.5-7B-Instruct or similar) served by
   **Ollama** on the Legion, reached the same way as the render endpoint
   (tunnel or Tailscale). Ollama's `/api/chat` with a JSON-schema `format`
   gives structured output without needing a bigger framework. Configured
   with `LOCAL_DIRECTOR_URL` / `LOCAL_DIRECTOR_MODEL`. Costs nothing beyond
   the electricity the Legion already uses for training and inference.
3. **Heuristic** - unchanged, always available, zero setup.

Ollama and ComfyUI share the Legion's 8GB card sequentially, not
concurrently: a generation job calls the director first (Ollama loads,
answers, and - with Ollama's default idle timeout - unloads), then the
render stage starts (ComfyUI loads SDXL). Neither needs to fit alongside
the other in VRAM at the same instant.

To turn this on: install Ollama on the Legion (`curl -fsSL
https://ollama.com/install.sh | sh` on Linux, or the Mac/Windows installer),
`ollama pull qwen2.5:7b-instruct`, then point `LOCAL_DIRECTOR_URL` at it
from the VPS's `.env` over the same tunnel/Tailscale link used for
`LEGION_INFERENCE_URL`.

## D8 - Free render quality wins (2026-08-30)

Once M4 was proven live end to end, the obvious next question was how to raise
output quality without new data or a paid API. The honest ceiling: this
project cannot and should not try to match frontier general-purpose image
models (GPT Image, Imagen) - those are a different scale of compute entirely.
The actual goal is narrower and those models cannot do it at all: this
designer's own visual language. What's free and worth doing now:

- **SDXL base+refiner two-stage pipeline** - the official way Stability AI
  designed SDXL 1.0 to be used, not a hack. Base composes for the first
  `SDXL_REFINER_SWITCH` fraction of steps (default 0.8), the refiner spends
  the rest on fine detail. `sdxl_workflow` in `backend/app/inference.py`
  builds the two-stage graph when `SDXL_REFINER_CHECKPOINT` is set, and
  degrades to the original single-stage graph when it isn't - so this stays
  working on a render machine that hasn't downloaded the refiner yet.
- **A fuller negative prompt** - the standard community SDXL negative prompt
  (`DEFAULT_NEGATIVE`) instead of four words, free, no extra model.
- **Deliberately not done now**: swapping the base checkpoint for a stronger
  community SDXL fine-tune (real quality lever, but couples the render
  checkpoint to whatever base the eventual style LoRA is trained against -
  revisit together once M3 actually trains); public layout dataset
  pretraining for the layout VLM (real, but the infra cost isn't worth
  paying before there is designer data to fine-tune on afterwards); a
  designer feedback loop on generated output (valuable, but needs the app,
  M5, to exist first).

## D9 - Legion tunnel: no-root Docker bridge, cron watchdog (2026-08-30)

Getting the VPS's Docker containers talking to services on the Legion (behind
home NAT/CGNAT, no public IP) needed working around two constraints on the
shared VPS: no passwordless sudo, and not wanting to touch system-wide sshd
config or firewall for other tenants' sake.

- **Direction**: reverse SSH tunnel, Legion dials out (`-R`) to the VPS -
  the only direction that works given the Legion has no public IP. Dedicated
  keypair (`legion_vps`), added to the VPS's `authorized_keys`, separate from
  any other key on that machine.
- **Ports**: `-R 18434:127.0.0.1:11434` (Ollama) and `-R 18188:127.0.0.1:8188`
  (ComfyUI), bound to the VPS's own loopback only (`GatewayPorts` left at its
  default `no` - deliberately not changed, since that's a system-wide sshd
  setting on a box other projects share).
- **Bridging loopback to Docker**: `backend/tools/legion_relay.py`, a small
  stdlib-only asyncio TCP relay, no root required (binding an already-
  configured local IP on a port >=1024 needs no privilege). It listens on
  `172.21.0.1` (the `ghostagent_default` Docker network's own gateway IP,
  which has no route from the public internet) and forwards to the
  loopback ports the tunnel bound. Containers on that network reach the
  Legion via `172.21.0.1:18434` / `:18188`.
- **The one thing that did need sudo**: UFW on the VPS defaults to deny
  incoming, so traffic from the Docker bridge subnet to those two ports was
  blocked even though the relay was listening. Fixed with two narrowly
  scoped rules the operator ran herself (`ufw allow from 172.21.0.0/16 to
  any port {18434,18188} proto tcp`) - open only to this project's own
  Docker network, not "Anywhere" like several other rules already on that
  box.
- **Resilience**: `backend/tools/legion_relay.crontab` - a per-minute
  watchdog (`pgrep ... || restart`) plus `@reboot`, installed with a plain
  user `crontab`, no root needed. On the Legion side, the tunnel itself
  needs the operator to set up a Task Scheduler task (`ssh -N ...` in an
  always-restart loop, trigger "at log on") since standing up a persistent
  outbound tunnel is a decision that has to come from her directly, not
  from a peer session or from me.

Env vars set from this: `LOCAL_DIRECTOR_URL=http://172.21.0.1:18434`,
`LEGION_INFERENCE_URL=http://172.21.0.1:18188` in the VPS's `backend/.env`.

## D10 - Refiner confirmed live, cu130 note (2026-08-30)

Base+refiner (D8) tested for real through the full VPS -> tunnel -> Legion path,
not just unit tests. Base stage 24 steps (~11s), refiner stage 6 steps (~3s),
total 36s (vs ~18s base-only) - the extra time is mostly the second checkpoint
load, not the refiner steps themselves. VRAM held 5.13GB free after the run
(7.37GB idle) on the 8GB card with --lowvram, no OOM. Visibly sharper output
than base-only on the same prompt.

ComfyUI logs a warning that cu130 (not cu128) would enable optimized CUDA ops
for this Blackwell card. Noted for a future pass, not applied now - the
Legion's disk is tight (24GB free after the refiner download) and this isn't
blocking anything.
