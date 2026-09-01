# 07. Quality strategy: closing the gap with the big image models

Written 2026-09-01, mid layout pretrain. This answers two questions we keep
coming back to: what does each training run actually buy us, and how does a
setup like ours (one 8GB laptop GPU, a CPU-only VPS, free-tier everything)
get anywhere near the quality of ChatGPT's image generation. Read 06 first
for the decisions this builds on.

## The honest ceiling

GPT-4o image generation runs on datacenter hardware, was trained on billions
of images, and understands prompts through a frontier language model. We will
not beat it at "draw me anything". Competing on generality is a losing game,
so we do not play it. Everything below is about winning a narrower game:
branded graphics in a learned aesthetic, for a specific market, repeatably.

## Why we can still win our lane

1. Specialize instead of generalize. A small model trained on the right
   narrow data beats a giant model at that narrow thing. The consented
   designer dataset, once the collector runs, is the part nobody can copy.
   That is the moat, not model size.

2. A pipeline of specialists instead of one big brain. An LLM plans the
   design, the layout model composes it, SDXL renders the image zones, a
   critic judges candidates and keeps the best, the face detailer fixes the
   known weak spot. Each piece fits in 8GB sequentially. The sum behaves far
   smarter than any single model we could run.

3. Typography by construction. GPT-4o has to paint letters into pixels and
   still gets them wrong sometimes. We never ask a diffusion model to spell:
   text lands on the canvas as real vector layers with real fonts, composited
   over the render. Our headlines are perfect by construction, at any size,
   editable after the fact. This is the one axis where the pipeline is
   structurally ahead of the big models, not behind.

4. Ride the open-source frontier. RealVisXL, Qwen, style loras: free, and
   improving every few months. When a better open checkpoint fits the card,
   we swap it in. The renderer is behind an interface for exactly this
   reason.

5. Rent muscle only when it counts. Training is the only thing that needs
   big hardware; serving does not. Anything above the 8GB ceiling (Flux lora
   training, 7B VLM full fine-tune) is a few hours on a rented cloud GPU, a
   few dollars one time, then the adapter comes home and runs locally
   forever.

6. Measure everything. Every quality change gets an eval harness the way
   faces did (docs/06 D20: mean 5.6 to 7.5, worst 2 to 7, tone spread 4.0 to
   0.0, all from one denoise number found by A/B). Without the harness we
   would have shipped vibes.

## The image quality ladder

Raw render quality, in order of cost. We climb top to bottom:

- Now: RealVisXL V5 + candidate generation + VLM critic + face detailer at
  0.25 denoise. This is the shipped baseline.
- Free, next: a second-pass hires upscale in ComfyUI (latent upscale plus
  low-denoise refine) for large canvases; more candidates per zone when the
  Legion is idle since candidates are pure quality-per-watt; per-subject
  negative prompts tuned from eval failures.
- Cheap: style loras from Civitai with licenses that allow commercial use of
  outputs (the GTA-style lora was the first; same pattern for any aesthetic
  the app offers as a preset).
- Rented-GPU tier: Flux or whatever open model leads at the time, lora-tuned
  on the designer dataset, inference either rented or quantized local if it
  fits by then.

## The layout ladder

- Rules (before today): every poster shares one skeleton. Predictable, stiff.
- Crello pretrain (running now): composition learned from 1,877 real designs,
  about 3,700 brief-to-layout examples over two epochs. Expected gains:
  variety between briefs, hierarchy that relates sizes and spacing, layouts
  that respond to content. Measured by rendering the same briefs through
  rules and model side by side and scoring them, same as the face matrix.
- Personal fine-tune (after the collector ships data): the designer's own
  layouts on top of the pretrain. Small personal datasets cannot teach design
  from zero but can teach an already design-literate model one person's
  habits. That was the point of the pretrain all along.

## What we never do for quality

No training on the designer's files outside the consent-gated path (CLAUDE.md,
docs/06 D14). No face datasets with unclear consent (docs/06 D19). A quality
win that costs trust is not a win.
