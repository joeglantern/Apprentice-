# training

Runs on the Lenovo Legion (RTX 5060, 8 GB). Pulls consented records from the VPS,
curates them, fine-tunes the two models, pushes checkpoints back. See
`docs/03` and `docs/06` D1 to D3.

## Setup on the Legion
```bash
python -m venv .venv && .venv/Scripts/activate      # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
# CUDA torch first. The RTX 5060 is Blackwell (compute capability sm_120), which cu124
# wheels do not carry kernels for (torch.cuda.is_available() lies and returns True, but
# any real op fails at runtime). Use the cu128 index, not cu124 - confirmed on this GPU:
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e ".[train]"
git clone https://github.com/kohya-ss/sd-scripts.git ../sd-scripts   # style LoRA trainer
python scripts/check_gpu.py
```
Environment, every session:
```
GHOST_API_URL=http://localhost:8000        # ssh tunnel to the VPS, or the hostname later
GHOST_API_TOKEN=<legion token from the VPS .env>
GHOST_DATA_DIR=D:\ghost-data                # somewhere with space; renders and models live here
```

## Nightly data flow
```bash
scripts/nightly_pull.sh
```
1. `ghost_training.pull`: incremental fetch of tagged records and export files through
   the API. Records without `consent.project_opted_in == true` are not downloaded.
2. `ghost_training.validate`: schema plus the consent check again on what is on disk.
3. `ghost_training.prepare`: renders PSDs to PNG (max 1024 px), writes kohya captions,
   the LayoutPrompter style layout text (`ghost_training.serialize`), and
   `style_profile.json` for the creative director.

Output: `data/curated/{style,layout,style_profile.json,dataset.json}`.

## Training
```bash
scripts/train_style_lora.sh v1                 # SDXL LoRA via kohya, configs/sdxl_lora_8gb.toml
python scripts/train_layout_vlm.py --version v1
```
Both write `data/checkpoints/<name>/run.json`. Push to the VPS registry:
```bash
python -m ghost_training.push data/checkpoints/style-lora-v1 --kind style-lora --base stabilityai/stable-diffusion-xl-base-1.0
python -m ghost_training.push data/checkpoints/layout-vlm-v1 --kind layout-vlm --base Qwen/Qwen2.5-VL-3B-Instruct
```

If the style run OOMs, set `resolution = "512,512"` in the toml before anything else.

## Tests
`pytest` runs on any machine without torch; it covers serialisation round trips, the
consent gate, captions, the style profile, and prepare on synthetic data.
