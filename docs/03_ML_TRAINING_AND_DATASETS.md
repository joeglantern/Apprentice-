# 03 - ML training and datasets

## 1. Two models, two jobs

| Model | Learns | Input data |
|---|---|---|
| Style LoRA (SDXL - see §2 for why Flux is a stretch goal, not the default) | The designer's visual texture - palette, rendering style, mood | Rendered exports + palette/color metadata |
| Layout VLM (Qwen2.5-VL-3B first, 7B as a later stretch - see §2) | Composition - bounding boxes, typography, z-ordering, spatial rhythm | The JSON layout schema from doc 01 §3 |

Train these separately. They have different data shapes, different loss
functions, and - importantly - different VRAM footprints, so decoupling them
means one model's requirements don't gate the other's.

## 2. Confirmed ceiling: RTX 5060 (mobile), 8GB GDDR7

This is fixed hardware, not a starting point to optimize down from - no
Legion configuration changes this number. It's below the comfortable range
for several of the options this doc originally left open, so here's what
that rules in and out concretely:

| Choice | At 8GB VRAM | Verdict |
|---|---|---|
| SDXL LoRA **training** | Workable, but genuinely at the edge - needs gradient checkpointing, 8-bit Adam, batch size 1, and 768px (not 1024px) to stay inside budget | **Do this first** |
| SDXL **inference** (serving the checkpoint later) | Comfortable, no tricks needed - training is the tight part, not inference | Confirms doc 01 §5's call to serve inference from the Legion |
| Flux LoRA training | Comfortable at ~24GB, workable quantized at ~12-16GB - 8GB is below the quantized floor even with NF4 + CPU offloading, and offloading makes it painfully slow | **Stretch goal only** - revisit if you rent a cloud GPU for a specific run, not a day-one target |
| Qwen2.5-VL-3B QLoRA | Fits with room to spare in 4-bit, even with gradient checkpointing off | **Do this first** |
| Qwen2.5-VL-7B / Llama-3.2-11B-Vision QLoRA | Technically possible in 4-bit with batch size 1, short sequences, and aggressive gradient checkpointing, but fragile - easy to OOM the moment image resolution or sequence length creeps up | Stretch goal once the 3B model is working end to end |

Practical read: build the whole pipeline - collector through Expo app -
against SDXL + Qwen2.5-VL-3B first. Both fit this GPU without fighting it.
Treat Flux and the larger VLM as later upgrades once there's a working v1
and, if you want them, a reason to rent a bigger GPU for a specific run
rather than try to make 8GB do more than it comfortably can.

Confirm this in code before a training run rather than trusting the doc:

```python
import torch
print(torch.cuda.get_device_name(0))
print(torch.cuda.get_device_properties(0).total_memory / 1e9, "GB")
```

## 3. Repos to build on rather than reinvent

- **`psd-tools`** (Python) - parsing PSD layer structure, already used by the
  collector in doc 02; reuse the same parser here for training-time re-extraction
  if the schema evolves.
- **`kohya-ss/sd-scripts`** - the most battle-tested SDXL/Flux LoRA trainer;
  has direct CLI support for exactly this workflow (image + caption pairs ->
  LoRA weights).
- **Hugging Face `diffusers`** `train_dreambooth_lora_sdxl.py` /
  `train_dreambooth_lora_flux.py` examples - a lighter-weight alternative to
  `sd-scripts` if you want to stay inside one framework end to end.
- **`LayoutParser`** - useful for benchmarking your layout model's output
  against a known document-layout-analysis baseline, even though your actual
  training data comes from the collector, not from `LayoutParser` itself.
- **"Awesome Layout Generation" curated lists** (search GitHub for the current
  one - these get renamed/forked often) - a map of academic layout-generation
  architectures worth skimming before you commit to the Qwen2.5-VL/Llama-3.2-V
  route, in case a purpose-built layout-generation model fits better than a
  general VLM for this specific sub-task.

## 4. Public datasets to benchmark against

Your real training data is the designer's own work - these are for sanity
checks and layout pretraining, not primary training data. Every entry below
was checked against its actual license page directly (docs/06 D11 caught a
summary-vs-reality gap on a checkpoint license the same way) rather than
trusted from a description, because this project may become paid work for
the designer's own business (LBA) - a non-commercial-only dataset is not
usable here even if it's the closest fit otherwise.

- **Crello** (`cyberagent/crello` on Hugging Face) - **recommended**.
  CDLA-Permissive-2.0, commercial use allowed. 23.3k real design layouts
  (former crello.com/VistaCreate templates: social posts, banners, posters)
  with per-element position, size, rotation, opacity, RGBA colour, and full
  text typography (typeface, size, weight, italic, alignment, line height,
  letter spacing) - close enough to this project's own Layer/Typography/
  Colour schema (doc 01 §3) that mapping one onto the other is mostly a
  rename, not a redesign. This is the one to pretrain the layout model on
  before the designer's own much smaller dataset.
- **Rico** - large mobile UI layout dataset; good for validating that your
  layout model's bounding-box/typography predictions are in a sane range
  before you trust it on scarce real data. Not poster-specific.
- **PubLayNet** - document layout analysis (text/title/figure/table regions);
  useful pretraining signal, but its documents are academic papers/forms,
  not posters - weaker composition signal than Crello for this use case.

Checked and rejected (or left unresolved) - keeping this list so nobody
re-spends the research time re-checking the same ones:

- ~~**CGL-Dataset / CGL-Dataset-v2**~~ - this section previously recommended
  it as "the closest public analogue" without checking the license first.
  It's CC BY-NC-SA 4.0 - non-commercial, so it's out for the same reason as
  D11's Juggernaut XL. Its annotation categories (logo/text/underlay/
  embellishment on real e-commerce ad posters) are still useful as a
  reference for schema design, just not as training data. Its ad copy is
  also Chinese-language, a weaker fit for LBA's market regardless of licence.
- **Poster100K** (`PosterCraft/Poster100K`) - CC BY-NC-SA 4.0 *and* the
  underlying images are real copyrighted movie/TV posters used under a
  "non-commercial research only" fair-use disclaimer - doubly blocked, not
  just a licence technicality.
- **PKU-PosterLayout** - gated behind signing an unpublished Release
  Agreement (emailed to the authors); its actual terms aren't public, so
  commercial-use compatibility can't be verified without requesting and
  reading it first. Don't adopt on the strength of the paper alone.
- **POSTAPosterArt** - license listed as "unknown" on its own dataset card.
  Also solves a narrower problem than the one we have (stylized text effects
  - metallic/3D lettering - not layout hierarchy/composition).
- **Contra Labs' creative-ad-design-dataset** - CC-BY-4.0, genuinely clear,
  but only 35 briefs / 105 images, explicitly a preview/eval set rather than
  training data. Worth keeping as a small human-crafted benchmark ("does our
  output look as good as a professional's for the same brief"), not as
  something to train on.

## 5. Data flow: nightly pull

```bash
# training/scripts/nightly_pull.sh
#!/usr/bin/env bash
set -euo pipefail

REMOTE="vps-tailnet:/data/ghostagent/curated/"
LOCAL="/mnt/training-data/latest/"

rsync -avz --delete "$REMOTE" "$LOCAL"
python training/scripts/validate_dataset.py "$LOCAL"
```

Run over Tailscale or a WireGuard tunnel rather than exposing the VPS's data
volume directly to the internet. `validate_dataset.py` should check the
schema from doc 01 §3 and reject any record missing `consent.project_opted_in`
as a second line of defense on top of the ingestion-time check in doc 02.

## 6. Example training commands, sized to the confirmed 8GB

Style LoRA (SDXL, via `diffusers`, tuned to actually fit 8GB rather than
assuming headroom that isn't there - lower resolution, lower rank, 8-bit
optimizer state):

```bash
accelerate launch train_dreambooth_lora_sdxl.py \
  --pretrained_model_name_or_path="stabilityai/stable-diffusion-xl-base-1.0" \
  --instance_data_dir="/mnt/training-data/latest/renders" \
  --output_dir="./checkpoints/style-lora-v1" \
  --resolution=768 \
  --rank=8 \
  --train_batch_size=1 \
  --gradient_accumulation_steps=4 \
  --gradient_checkpointing \
  --use_8bit_adam \
  --enable_xformers_memory_efficient_attention \
  --learning_rate=1e-4 \
  --lr_scheduler="constant" \
  --max_train_steps=1500 \
  --mixed_precision="bf16"
```

If this still OOMs on a full run, the next lever is `--resolution=512`
before touching rank or batch size further - resolution has the biggest
memory impact of any of these flags.

Layout VLM (Qwen2.5-VL-**3B**, QLoRA via `peft` - the 3B variant specifically
because it comfortably fits 8GB where the 7B model would be fighting for
room on every batch):

```python
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="bfloat16")
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct", quantization_config=bnb_config, device_map="auto"
)
model.gradient_checkpointing_enable()
lora_config = LoraConfig(
    r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"], lora_dropout=0.05,
)
model = get_peft_model(model, lora_config)
# Train model to map a rendered image -> the JSON layout schema from doc 01 §3,
# using the curated dataset pulled in §5 as (image, target_json) pairs.
# Keep batch_size=1 with gradient accumulation, and cap image resolution
# before tokenizing - visual-token count is what actually drives memory
# use for a VLM, more than model size alone.
```

Once the 3B model is working end to end, the same script with
`Qwen/Qwen2.5-VL-7B-Instruct` is the natural next experiment - just expect
to drop batch size and image resolution further, and don't be surprised if
it needs a rented GPU for that specific run rather than the Legion.

Push both checkpoints back to the VPS's model registry (a plain
`checkpoints/` folder in object storage is enough at this scale - no need
for a full model registry service yet) once a run completes, per the
architecture in doc 01.
