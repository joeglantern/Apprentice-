"""Push a finished checkpoint folder to the VPS registry.

    python -m ghost_training.push data/checkpoints/style-lora-v1 --kind style-lora \
        --base stabilityai/stable-diffusion-xl-base-1.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ghost_training.api import GhostApi
from ghost_training.config import load_config

UPLOAD_SUFFIXES = {".safetensors", ".json", ".txt", ".toml", ".yaml", ".yml", ".md", ".png"}


def push(api: GhostApi, folder: Path, kind: str, base_model: str) -> list[str]:
    name = folder.name
    run_file = folder / "run.json"
    run = json.loads(run_file.read_text(encoding="utf-8")) if run_file.exists() else {}
    api.register_checkpoint(name, kind, base_model, run)
    uploaded: list[str] = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in UPLOAD_SUFFIXES:
            api.upload_checkpoint_file(name, path)
            uploaded.append(path.name)
    return uploaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--kind", choices=["style-lora", "layout-vlm"], required=True)
    parser.add_argument("--base", required=True, help="base model id")
    args = parser.parse_args()
    cfg = load_config()
    api = GhostApi(cfg.api_url, cfg.api_token)
    try:
        uploaded = push(api, args.folder.resolve(), args.kind, args.base)
    finally:
        api.close()
    print(f"pushed {args.folder.name}: {', '.join(uploaded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
