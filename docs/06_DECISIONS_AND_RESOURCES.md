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
