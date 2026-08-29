---
name: lora-training-ops
description: Conventions for kicking off, monitoring, and checkpointing LoRA and VLM fine-tuning runs on the Lenovo Legion. Use when writing or running anything under training/.
---

# LoRA / VLM training ops (Lenovo Legion)

Spec: `docs/03_ML_TRAINING_AND_DATASETS.md`. Hardware is confirmed and
fixed - **RTX 5060 mobile, 8GB GDDR7, 32GB system RAM**. Size everything to
that; do not plan around headroom that isn't there.

## Before every run
1. Confirm the GPU in code, not from memory:
   ```python
   import torch
   print(torch.cuda.get_device_name(0))
   print(torch.cuda.get_device_properties(0).total_memory / 1e9, "GB")
   ```
2. Pull and validate data: `training/scripts/nightly_pull.sh` -> rsync over
   Tailscale/WireGuard from `vps-tailnet:/data/ghostagent/curated/` to
   `/mnt/training-data/latest/`, then `validate_dataset.py` which enforces
   the doc 01 §3 schema and **drops any record without
   `consent.project_opted_in == true`**.
3. Never train on data that did not come through that path.

## Model choices (fixed for v1)
| Job | Model | Why |
|---|---|---|
| Style LoRA | SDXL base 1.0, rank 8, 768px | Fits 8GB with tricks; Flux does not |
| Layout VLM | Qwen2.5-VL-3B-Instruct, QLoRA 4-bit, r=16 | Fits with room; 7B is a stretch goal |

Flux LoRA and 7B/11B VLMs are **stretch goals** that most likely need a
rented GPU for that specific run. Do not default to them.

## Reference commands
Style LoRA (diffusers `train_dreambooth_lora_sdxl.py`):
`--resolution=768 --rank=8 --train_batch_size=1 --gradient_accumulation_steps=4 --gradient_checkpointing --use_8bit_adam --enable_xformers_memory_efficient_attention --learning_rate=1e-4 --lr_scheduler=constant --max_train_steps=1500 --mixed_precision=bf16`

If it OOMs: drop `--resolution` to 512 **first** - resolution dominates
memory - before touching rank or batch size.

Layout VLM: `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="bfloat16")`,
`gradient_checkpointing_enable()`, `LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj","v_proj"], lora_dropout=0.05)`,
batch size 1 with accumulation, and **cap image resolution before
tokenising** - visual token count drives VLM memory more than model size.

## Run hygiene
- One run = one output dir: `training/checkpoints/<model>-v<N>/` with a
  `run.json` (args, dataset hash, git SHA, start/end, final loss).
- Log to stdout + a file in the run dir; watch with `nvidia-smi -l 5` in a
  second terminal.
- Save a checkpoint at least every 250 steps so an OOM late in a run
  doesn't lose everything.
- Get **one full run to a usable checkpoint before optimising anything**.

## Checkpoint push-back
On completion, push the LoRA weights (+ `run.json`) to the VPS's object
storage under `checkpoints/<model>-v<N>/`. A plain folder is the registry;
no registry service. The inference gateway lists that folder to populate
the app's aesthetic selector.

## Inference note
Inference runs on the Legion too (SDXL inference is comfortable in 8GB).
Training and inference contend for the same GPU - the gateway falls back to
burst GPU rental while a training run holds the card.
