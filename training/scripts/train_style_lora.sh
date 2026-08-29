#!/usr/bin/env bash
# Train the SDXL style LoRA with kohya-ss/sd-scripts (docs/06 D2).
# One time setup on the Legion:
#   git clone https://github.com/kohya-ss/sd-scripts.git ../sd-scripts
#   (follow its README to install into the same venv; needs the CUDA torch build)
# Usage: scripts/train_style_lora.sh [version]   e.g. v2 (default v1)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VERSION="${1:-v1}"
NAME="style-lora-$VERSION"
SD_SCRIPTS="${SD_SCRIPTS:-../sd-scripts}"
CONFIG="configs/sdxl_lora_8gb.toml"
OUT="data/checkpoints/$NAME"

python scripts/check_gpu.py
test -f data/curated/dataset.json || { echo "run scripts/nightly_pull.sh first" >&2; exit 1; }
mkdir -p "$OUT"

START=$(date -Is)
python - "$CONFIG" "$OUT" "$NAME" <<'PY'
import sys, pathlib
cfg, out, name = sys.argv[1:4]
text = pathlib.Path(cfg).read_text()
text = text.replace('output_dir = "data/checkpoints/style-lora-v1"', f'output_dir = "{out}"')
text = text.replace('output_name = "style-lora-v1"', f'output_name = "{name}"')
text = text.replace('logging_dir = "data/checkpoints/style-lora-v1/logs"', f'logging_dir = "{out}/logs"')
pathlib.Path(out, "config.toml").write_text(text)
PY

accelerate launch --num_cpu_threads_per_process 2 \
  "$SD_SCRIPTS/sdxl_train_network.py" --config_file "$OUT/config.toml" 2>&1 | tee "$OUT/train.log"

python - "$OUT" "$START" <<'PY'
import json, pathlib, subprocess, sys, datetime
out, start = sys.argv[1:3]
sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dataset = json.loads(pathlib.Path("data/curated/dataset.json").read_text())
run = {
    "kind": "style-lora",
    "base_model": "stabilityai/stable-diffusion-xl-base-1.0",
    "trainer": "kohya-ss/sd-scripts sdxl_train_network.py",
    "config": "config.toml",
    "dataset_hash": dataset["dataset_hash"],
    "style_images": dataset["style_images"],
    "git_sha": sha,
    "started_at": start,
    "finished_at": datetime.datetime.now(datetime.UTC).isoformat(),
}
pathlib.Path(out, "run.json").write_text(json.dumps(run, indent=2))
print(json.dumps(run, indent=2))
PY

echo "Push with: python -m ghost_training.push $OUT --kind style-lora --base stabilityai/stable-diffusion-xl-base-1.0"
