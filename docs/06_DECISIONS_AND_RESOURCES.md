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

## D11 - Base checkpoint and face-detail tooling: researched, not adopted yet (2026-08-30)

Looked for free upgrades to the render stage beyond the base+refiner pipeline (D8).

- **Juggernaut XL** (a well-known SDXL community fine-tune) - checked its actual
  license rather than trust a summary: it explicitly forbids deploying the model
  "behind paid API services" without separate commercial licensing from
  RunDiffusion. Given this project may become paid work for the designer's own
  business (LBA), that is a real constraint, not a technicality. Not adopted.
- **DreamShaper XL** - genuine OpenRAIL++ (the same licence as official SDXL
  base, no extra restriction found), but the readily-available variant is a
  "turbo" build tuned for 4-8 step / low-cfg sampling, which is not a drop-in
  replacement for our 30-step base+refiner graph without separately re-tuning
  sampler settings. Left for a future pass once there is time to verify a
  standard (non-turbo) build and test it properly rather than swap blind.
- **ComfyUI-Impact-Pack's FaceDetailer** (fixes small/distorted faces, a known
  SDXL weakness, exactly the failure mode seen in the group-shot generations) -
  code is GPL-3.0, which is fine for our use (that licenses the tool, not images
  produced with it). Not adopted yet for a different reason: its real node graph
  has on the order of twenty interconnected inputs and the exact wiring could
  not be confirmed with confidence from documentation alone. Building it blind
  against a remote machine, with no fast local iteration loop, risked breaking
  a render pipeline that already works. Worth revisiting with either live
  ComfyUI-side testing (someone iterating in the actual node editor) or a
  known-good exported workflow JSON to start from, rather than a hand-built
  graph.

Net effect: stayed on official `sd_xl_base_1.0.safetensors` (Stability AI's own
OpenRAIL++ licence, zero restriction found) plus the existing refiner. Added
instead: a hires-fix second pass (upscale + light re-render), same category of
technique as the refiner, no new licence questions, no new dependencies.

## D12 - Hires-fix tested live, not adopted (2026-08-30)

Tested the optional hires-fix pass (D11) for real on the Legion, at 1.5x scale,
0.4 denoise, 12 steps.

VRAM (measured by the Legion, nvidia-smi): peaked at 7535 MiB used out of 8151
total - only ~365 MiB free at the tightest point of the three-pass run (base,
refiner, hires). It completed without an OOM this time, but that is a thin
enough margin that any concurrent GPU load (the desktop itself, a browser tab)
could push it over on a different run.

More importantly: the output was worse, not better. The same jazz-festival
prompt that had rendered cleanly through base+refiner alone came back with
visible streaky, smeared artefacting on trees and the figure once the hires
pass ran on top - not the subtle detail sharpening a hires-fix is supposed to
add. Whether that is the denoise value, the upscale method, or genuine
incompatibility with this graph was not root-caused; not worth the VRAM risk
to find out for a result that already looks worse.

Decision: left `SDXL_HIRES_SCALE=1.0` (disabled) on the VPS - back to base+
refiner only, which is the version that has consistently produced the good
results throughout this session. The code stays in the repo, off by default,
in case a lower denoise value or a different upscale method is worth trying
later; not a priority right now given base+refiner alone is already working
well.

## D13 - Two auth gaps closed in the app's own data paths (2026-08-30)

Neither was reported; both turned up doing a pass over how the app actually
authenticates against the backend, once the generation-history feature made it
worth checking end to end.

- **Rendered layer images had no auth at all.** `CanvasPreview.tsx` was
  rendering `layer.raster_url` straight from the backend's JSON response - a
  relative, unauthenticated path meant as a human-readable hint, not something
  a client can fetch. `verify_agent_token` now also accepts the agent token as
  a `?token=` query param (a header-only check can't work here: react-native-svg's
  `Image` href can't carry an `Authorization` header), and a bad query token can
  never override a valid header or vice versa. `CanvasPreview` now builds the
  real URL itself via `rasterUrl(jobId, layerId)` instead of trusting the
  field.
- **The Socket.IO progress channel had no auth at all.** `join()` would put any
  connecting client into any job's progress room just by knowing or guessing
  its `job_id` - every REST route in this API sits behind a bearer token, this
  one didn't. `connect()` now checks the same token before the handshake
  succeeds, and `join()` separately checks that the connecting agent is the one
  who actually requested that job before it's let into the room - connecting
  with a valid token doesn't imply the right to watch just any job.

Both are covered by tests now (`test_query_param_token_is_a_fallback_not_a_bypass`,
`test_realtime.py`). `list_jobs` was also changed at the same time to select
only the summary columns the history list actually reads, not full rows with
`plan`/`result`, which can be large and were never read by that view.

Follow-up the same day: a code review of this diff caught that the query-token
fallback had been added to the *shared* auth dependency, not scoped to the
raster route alone - every authenticated route accepted it, putting the agent
token in a URL (and so in access logs) far beyond the one route that actually
needed it. Split into `verify_agent_token` (header-only, everywhere) and
`verify_agent_token_or_query` (raster route only); `test_query_param_token_is_a_fallback_not_a_bypass`
was replaced by `test_query_param_token_is_not_accepted_outside_the_raster_route`
in test_ingest.py plus a new positive test on the raster route itself in
test_generate.py. Also fixed in the same pass: `join()` was pulling the whole
Job row (plan/result included) just to check one column, and wasn't
lowercasing the incoming room id the way read_job/read_raster already do.

Separately, found live: the worker's `--concurrency=2` let two `generate_design`
renders hit the Legion's single 8GB GPU at once - two of four jobs in a test
batch timed out from VRAM contention while the other two rendered fine.
Dropped to `--concurrency=1`; renders are GPU-bound and must be serialized,
tagging tasks are cheap enough to queue behind one.

## D14 - Layout/graphic-design datasets: checked licenses, corrected an earlier recommendation (2026-08-30)

The actual problem behind "the text doesn't look like a poster" isn't the
renderer - `layout.py`'s `heuristic_layout` is one fixed template (background
block, image column, a vertical stack of text boxes) applied identically to
every prompt, with no learned sense of hierarchy or composition. That's the
stand-in doc 03 always said would be replaced by the trained layout model;
fixing the look-and-feel means giving that model something real to learn
composition from before the designer's own (much smaller) dataset arrives.

Checked every candidate's actual license page directly rather than a search
summary, the same way D11 caught the Juggernaut XL restriction - this project
may become paid work for the designer's own business (LBA), so a
non-commercial-only dataset is not usable here regardless of fit:

- **Crello** (`cyberagent/crello`) - CDLA-Permissive-2.0, commercial use
  allowed. 23.3k real design layouts with per-element position, size,
  rotation, opacity, RGBA colour, and full text typography - maps closely
  onto this project's own Layer/Typography/Colour schema. Adopted as the
  layout model's pretraining set.
- **CGL-Dataset / CGL-Dataset-v2** - doc 03 previously recommended this as
  "the closest public analogue" without a license check. It's CC BY-NC-SA
  4.0, non-commercial - corrected in doc 03 §4. Its annotation schema is
  still a useful reference for category design, just not usable as training
  data; its ad copy is Chinese-language too, a weaker fit regardless.
- **Poster100K** - CC BY-NC-SA 4.0 *and* the images are real copyrighted
  movie/TV posters under a non-commercial-research-only fair-use disclaimer.
  Doubly blocked, not adopted.
- **PKU-PosterLayout** - gated behind an unpublished Release Agreement (sent
  by emailing the authors); terms aren't public, so commercial-use fit can't
  be verified without requesting it first. Not adopted on the paper alone.
- **POSTAPosterArt** - license listed as "unknown" on its own dataset card,
  and solves a narrower problem (stylized text effects) than the layout/
  hierarchy gap this project actually has. Not adopted.
- **Contra Labs' creative-ad-design-dataset** - CC-BY-4.0, genuinely clear,
  but only 35 briefs/105 images - a preview/eval set, not training data.
  Kept as a small benchmark for "does our output look as good as a
  professional's for the same brief," not for training.

Full writeup with the schema comparison in doc 03 §4.

## D15 - Posters laid out like posters; typefaces; Flux for in-photo words (2026-08-30)

The first full posters through the pipeline looked like a photo slapped beside some
text, and that was accurate: `layout.py` was building a web hero (image boxed in a
right column, flat colour block, small text stacked left), because nothing in the
pipeline could put type over a photo legibly, so it never tried. Fixed as one unit:

- **Poster recipe.** Full-bleed photo rendered at the canvas aspect; a scrim over
  the text zone (left on landscape, bottom on portrait) that fades into the photo
  through stepped bands (the layer schema has no gradients); a type stack anchored
  to the bottom of the zone: letter-spaced uppercase eyebrow, accent bar, headline
  at no less than 7.5 percent of canvas width, subhead, details one per line, a
  filled button. Contrast is checked against the scrim as it composites over a
  photo. `logo` becomes a small wordmark, never the literal words "X logo".
- **Director writes poster copy** (five-word headline, eyebrow, details as lines,
  cta), gets two full example plans in the prompt (a small local model moves far
  more on examples than on rules), and is told: Kenyan phone numbers and prices,
  dates at least two weeks out written the poster way, no placeholders, omit the
  logo element rather than invent a brand. Thinking models get `think: false`.
- **Renderer told to leave room.** Every background prompt ends with clean negative
  space / no text / no letters; "letters, words, typography, signage, logo" joined
  the negative prompt. SDXL's own lettering was the source of the gibberish.
- **Typefaces.** Arial was the weakest thing on the page. Four OFL faces are
  bundled in `app/assets/fonts` (Inter, Bebas Neue, Playfair Display, Space
  Grotesk); the director picks a pairing per piece by mood; the designer's own
  dominant font still wins once a profile exists.
- **Words inside the photograph.** SDXL cannot spell. An image element may carry
  `scene_text` (one to three words on a sign or banner, only when the brief asks);
  that layer alone renders with FLUX.1-schnell (Apache 2.0, checked) as a Q4_K_S
  GGUF through ComfyUI-GGUF, which fits the 8GB card. Set `FLUX_UNET` to enable;
  without it the layer falls back to SDXL and the words are simply absent.
  Everything else stays real type on top, which is the only way copy is guaranteed
  correct - this is the lane, not "make the image model write the poster".
- **Default canvas** is now 1080x1350 portrait.
- **Planner model.** Moving from qwen2.5:7b-instruct to qwen3:8b (both fit at
  Q4); the placeholder and 555-number mistakes were model strength, not prompt.
- **Worker concurrency** stays at 1: two renders at once on one 8GB GPU time out.

Crello (D14) in practice: the dataset card's schema is wrong. Streaming produced
nothing in ten minutes because the element previews share the parquet shards with
the layout columns; shards are downloaded whole and read column-wise with pyarrow.
`type`, `font`, `text_align`, `category`, `format` are integer class labels whose
names live in the parquet metadata; boxes are absolute pixels; colours are rgba
strings; bold is per character. One shard (500 MB) yields 626 usable layouts;
the full train split is 31 shards, about 15 GB, which the Legion cannot hold until
the 70 GB OneDrive cache is dealt with (C: was at 6.6 GB free; clearing the npm
cache alone recovered 17.8 GB).

## D16 - Compositions, date badges, and image/logo kinds (2026-08-30)

Operator asked for posters that differ from each other, mixed faces, colours and
sizes, date badges, icons, and for standalone photographs and logos alongside posters.

- **Three compositions**, chosen by the director per brief: `anchor` (type
  bottom-left over the photo), `centered` (type centred low, longer fade), `split`
  (a solid palette panel carries the type, the photo fills the rest, nothing sits on
  the photo). The director is told not to default to one.
- **Date badge**: a round accent disc top-right with the day large and the month
  small, only for dated events. First non-rectangular shape in the layer schema
  (`shape: "ellipse"`), drawn by the app and the compositor.
- **Mixed colour**: eyebrow and subhead take the accent; headline and details the
  foreground. The accent is now the most saturated mid-tone in the palette rather
  than the brightest colour, which on the default palette was white.
- **Kinds**: `poster` (director, layout, render), `image` (one photograph, no
  director), `logo` (one flat mark on white). A logo brief that names the brand in
  quotes passes it as `scene_text`, so the Flux path sets the real letters. New
  `jobs.kind` column, migration 0004. The prompt screen gets a plain three-way
  selector; Claude Design owns the look.
- **Icons**: Tabler Icons (MIT), seven outline glyphs bundled in `app/assets/icons`.
  Each detail line gets one chosen from what it says (date, time, place, price,
  phone, handle); a new `icon` layer type, drawn by the app from a path table.
- **Flux verified live.** The Q4_K_S GGUF plus T5 Q4_K_S, CLIP-L and the VAE
  (from an ungated mirror, SHA-256 checked against the official file) run on the
  8GB card through ComfyUI-GGUF. A logo brief for "Umoja Threads" came back with
  the name set correctly in clean type; SDXL's attempt at the same brief read
  "UMOIATHEARD". Flux is used only where words must be inside the picture.
- **Photoreal humans and animals**: SDXL base is adequate; the free upgrade to
  check next is a photoreal SDXL fine-tune (RealVisXL) - license to be read
  directly before adopting, as with D11.

## D17 - Two-seed judge (2026-08-30)

SDXL's bad outputs are a minority: a stray letter, a mangled hand, the subject parked
where the type goes. `RENDER_CANDIDATES=2` renders two seeds per image layer and
Qwen2.5-VL 3B (Ollama, same instance as the director, `CRITIC_MODEL`) scores them
on brief match, photographic cleanliness, absence of lettering, negative space in
the text zone, and anatomy, then picks one. One extra render per poster; off by
default until measured on a batch. Any judge failure keeps the first render.
Layers with `scene_text` (Flux) are not double rendered.

What would move quality further, in order: RealVisXL as the photo checkpoint
(license to read first), an East African context LoRA from CC-BY/CC0 Wikimedia
Commons photographs so "Nairobi" stops looking generic, brand kits (palette plus
logo file carried by a brief so a series stays on-brand), the Crello layout
pretraining (D14, blocked on disk), and an edit loop in the app (re-render just
the photo, swap composition or typeface without replanning).

## D18 - Face detail pass; the face dataset question; a tunnel postmortem (2026-08-30)

Operator flagged bad faces, teeth and fingers and asked about face datasets
(African-focused). The honest analysis: these are architectural SDXL weaknesses -
a face in a full-scene render gets a few dozen pixels - not missing training
data, so a dataset fine-tune is the weakest and most expensive fix. What shipped
instead: after every SDXL render, face_yolov8m (Apache 2.0 weights from
Bingsu/adetailer, verified) detects each face and Impact Pack's FaceDetailer
re-renders it at guide size 512 with the same stage's model and prompts. The
FaceDetailer field set was taken from the live /object_info schema, not
documentation - the D11 lesson, and this time it worked on the first try.
FACE_DETAIL=0 disables. hand_yolov8s.pt is downloaded for a future hand pass.

Datasets, licenses read directly: FairFace is genuinely CC BY 4.0 and balanced
across race - adopted for *evaluating* our outputs across skin tones, not for
training on faces (consent and biometric-law risk on a project that may become
paid work). CelebA, FFHQ and the Kaggle "African faces" sets are research-only
or unclear - not adopted. RealVisXL V5.0 is clean OpenRAIL++ (checked the model
card raw - no extra restriction, unlike Juggernaut in D11) and is the adopted
next photoreal upgrade, blocked at 4.5 GB free disk until the OneDrive cache
(70 GB) is dealt with.

Postmortem, for the next person debugging "the tunnel is up but hangs": tonight's
S4U scheduled-task change moved ComfyUI and the tunnel into session 0, where a
non-elevated shell cannot kill them (WMI shows an empty command line; taskkill
silently fails). A ComfyUI predating the ultralytics install held port 8188 that
way until an elevated taskkill cleared it. Separately, killing tunnel clients
without TCP teardown leaves sshd on the VPS holding the remote-forward binds for
a session whose client is gone - every new tunnel then fails its bind
(ExitOnForwardFailure) and loops, while connections into the stale binds hang
forever. The fix was killing the stale sshd session server-side; the lasting
lesson is that the VPS sshd has no ClientAliveInterval, so dead remote-forward
sessions never expire on their own.

## D19 - RealVisXL adopted; brand kits; hand pass shipped (2026-08-31)

A/B on the same tailoring-workshop portrait brief, full pipeline both sides:
official base+refiner vs RealVisXL V5.0 fp16 with no refiner (community practice
for fine-tunes). RealVisXL won clearly - skin with real photographic
micro-texture instead of the airbrushed SDXL sheen, believable fabric, saner
prompt adherence - and runs a simpler, lighter graph. Adopted as the production
checkpoint (`SDXL_BASE_CHECKPOINT=RealVisXL_V5.0_fp16.safetensors`, refiner
empty). The official checkpoints stay on the Legion's disk; rollback is one env
flip. License: OpenRAIL++, read from the model card raw in D18.

Brand kits shipped end to end: a request may carry `brand: {name, palette,
typeface}`; the director treats it as binding across all three backends
including the heuristic fallback, jobs store it (migration 0005), and the app
grew a collapsible name/palette input. The hand-detail pass (hand_yolov8s,
denoise 0.35) chains after the face pass and shipped in the same window.

The v12 portrait set is the face-quality evidence: eight face-heavy briefs -
laughing grandmother, barbershop, bride, runners, teacher, fisherman, dancers,
DJ - all with clean teeth, eyes and hands through the detail passes.

## D20 - Revise loop, face-integrity harness; smoke-tested live (2026-08-31)

POST /generate/{id}/revise turns a finished poster into a new job with the same
plan and a composition or typeface override, skipping the director, and reuses
the already rendered photo unless a fresh one is asked for - a tweak costs
seconds instead of a full pipeline run (migration 0006 stores provenance). The
canvas screen grew plain chips for it. Smoke-tested live together with brand
kits: a branded Umoja Threads brief came back with the exact bound palette and
typeface, and its split revision reused the raster.

ghost_training/eval_faces.py is the face-integrity harness: a fixed, append-only
portrait matrix across skin tones, ages, a group and a hands shot, rendered
through the production pipeline and scored by the local VLM; the report carries
the mean, the worst row, and the skin-tone spread as the bias signal. First
baseline run pending a quiet render queue.

The harness paid for itself on its first outing. Baseline and a rerun both came
back mean 5.6-5.9 with the light-skin rows at 2: a repeating knit-weave texture
grafted across otherwise clean faces. A dedicated face-prompt conditioning fix
changed nothing, so the mechanism was hunted empirically: the same brief rendered
three ways (face detail denoise 0.45, 0.25, and the pass disabled) showed 0.45
producing the weave and both others clean. RealVisXL already renders large
portrait faces well; the detail pass at 0.45 was re-imagining them and amplifying
the model's fabric prior into skin. Default dropped to 0.25, which leaves large
faces alone while still repairing the small-face mush the pass exists for.
Post-fix matrix: mean 7.5 (from 5.62), worst row 7 (from 2), tone spread 0.0
(from 4.0), and the previously failing rows verified clean by eye.

## D21 - Layout pretrain v1 trained; paged optimizer crashed the machine (2026-09-01)

The Crello layout pretrain (docs/06 D14) completed: Qwen2.5-VL-3B, qlora r16
nf4, 1,877 layouts, 2 epochs, 236 steps in 1h52 on the Legion. Train loss
2.3 to 0.69. Adapter and run.json at
training/data/checkpoints/layout-pretrain-v1/final.

Two launches before it died taught us the hard lesson: paged_adamw_8bit's
unified-memory optimizer state hangs torch.save at every 50-step checkpoint
on this machine and thrashes the whole system until it hard-crashes
(Kernel-Power 41, twice, both at the step-50 save). Fixes that stuck: plain
adamw_8bit (state on-GPU, saves normally), checkpoints every 50 steps with
save_total_limit 2, resume that skips checkpoints lacking trainer_state.json,
and the run launched detached via Start-Process so session restarts cannot
kill it. Rule for every future run on this box: never paged optimizers.

Smoke test and rules-vs-model comparison pending; the adapter is not wired
into the backend yet.

## D22 - Chat understands the message instead of guessing at it (2026-09-02)

The chat screen wrote its own assistant lines and sent every free-text message
to /generate, so "make the headline shorter" replaced the poster instead of
changing it. The thread also lived in component state, which meant a reload lost
the conversation while the jobs it produced survived.

Now a turn is a request. POST /chat/{id}/turn hands the message, the last eight
turns and a compressed summary of the open piece to a model that returns one
structured object: an action (revise, edit_copy, new_direction, answer, clarify),
its payload, and the sentence the user reads. Routing and reply come from the same
call so the reply cannot promise one thing while the router does another.
edit_copy patches the plan's text elements and reuses the photograph, which makes
a copy change cost the type pass rather than a full render.

Three rules the implementation holds to:

- Fail closed. An unusable model answer, a job that has not finished, a thread at
  its render cap - all degrade to `answer`. Nothing degrades to starting a render
  nobody asked for.
- The reply is written before the render runs, so it may only state an intent. A
  second `landed` line, generated deterministically from what the job actually did,
  is the only sentence allowed to describe a result. It is settled when the thread
  is read, so the worker knows nothing about chat.
- Quick-action chips carry their intent as a field and skip the model entirely.
  A known intent should not be paid for twice, and cannot be misrouted.

Two things that had to be measured rather than assumed, both in
backend/tools/chat_route_eval.py:

- Ollama's grammar compiler rejects minLength/maxLength with a 400 the ladder
  reads as "model unreachable". The whole local path would have sat silently in
  the deterministic fallback. The schema sent as `format` is now stripped of
  validation-only keywords; Pydantic still checks the values on the way back.
- Model choice. On the fifteen-message routing set, qwen3:8b (thinking off)
  routes 15/15 with a median 1.1s resident; qwen2.5:7b-instruct, the director's
  model, routes 6/15 and five of its answers fail validation twice over. CHAT_MODEL
  therefore defaults to qwen3:8b, separately from LOCAL_DIRECTOR_MODEL. Field order
  in the response schema is load-bearing for the same reason: `action` is emitted
  before `reply`, so the sentence is written knowing the route.

Claude stays the top of the ladder when a key is set, at effort low rather than
the director's high - a turn is one routing decision and a sentence, and it sits
on the path of every message.
