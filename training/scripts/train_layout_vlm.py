"""QLoRA fine-tune of Qwen2.5-VL-3B-Instruct to map a rendered design to its layout text.

Input:  data/curated/layout/train.jsonl from ghost_training.prepare
Output: data/checkpoints/layout-vlm-<version>/ (adapter weights + run.json)

Sized for an 8 GB card: 4-bit base, r=16 LoRA on attention projections, batch 1 with
gradient accumulation, images capped at 768 px on the long side before tokenising
(visual token count is what drives memory). Run scripts/check_gpu.py first.

    python scripts/train_layout_vlm.py --version v1 --epochs 3
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
PROMPT = (
    "You are a layout model trained on one designer's work. Describe the layout of this "
    "design as layout text: one line per element using <canvas>, <text>, <shape> and "
    "<image> tags on a 0..1000 grid."
)


def load_examples(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise SystemExit(f"no layout examples in {path}; run scripts/nightly_pull.sh first")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--accum", type=int, default=8)
    parser.add_argument("--max-side", type=int, default=768)
    parser.add_argument("--data", type=Path, default=Path("data/curated"))
    parser.add_argument("--out", type=Path, default=Path("data/checkpoints"))
    parser.add_argument("--save-every", type=int, default=250)
    args = parser.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model
    from PIL import Image
    from transformers import (
        AutoProcessor,
        BitsAndBytesConfig,
        Qwen2_5_VLForConditionalGeneration,
    )

    out_dir = args.out / f"layout-vlm-{args.version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    examples = load_examples(args.data / "layout" / "train.jsonl")
    random.Random(42).shuffle(examples)
    started = datetime.now(UTC).isoformat()

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        BASE_MODEL, quantization_config=bnb, device_map="auto", torch_dtype=torch.bfloat16
    )
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    processor = AutoProcessor.from_pretrained(
        BASE_MODEL, min_pixels=256 * 28 * 28, max_pixels=args.max_side * args.max_side
    )
    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad), lr=args.lr, weight_decay=0.0
    )

    def encode(example: dict[str, Any]) -> dict[str, torch.Tensor]:
        image = Image.open(args.data / example["image"]).convert("RGB")
        image.thumbnail((args.max_side, args.max_side))
        messages = [
            {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": PROMPT}],
            },
            {"role": "assistant", "content": [{"type": "text", "text": example["text"]}]},
        ]
        text = processor.apply_chat_template(messages, tokenize=False)
        batch = processor(text=[text], images=[image], return_tensors="pt")
        labels = batch["input_ids"].clone()
        # Only learn the assistant turn: mask everything up to and including the prompt.
        prompt_only = processor.apply_chat_template(
            messages[:1], tokenize=False, add_generation_prompt=True
        )
        prompt_len = processor(text=[prompt_only], images=[image], return_tensors="pt")[
            "input_ids"
        ].shape[1]
        labels[:, :prompt_len] = -100
        batch["labels"] = labels
        return {k: v.to(model.device) for k, v in batch.items()}

    model.train()
    step = 0
    losses: list[float] = []
    log = (out_dir / "train.log").open("a", encoding="utf-8")
    t0 = time.time()
    for epoch in range(args.epochs):
        for i, example in enumerate(examples):
            batch = encode(example)
            loss = model(**batch).loss / args.accum
            loss.backward()
            losses.append(loss.item() * args.accum)
            if (i + 1) % args.accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                step += 1
                if step % 10 == 0:
                    recent = sum(losses[-10 * args.accum :]) / len(losses[-10 * args.accum :])
                    msg = f"epoch {epoch} step {step} loss {recent:.4f} {time.time() - t0:.0f}s"
                    print(msg)
                    log.write(msg + "\n")
                    log.flush()
                if step % args.save_every == 0:
                    model.save_pretrained(out_dir / f"step-{step}")
    model.save_pretrained(out_dir)
    processor.save_pretrained(out_dir)

    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    dataset = json.loads((args.data / "dataset.json").read_text(encoding="utf-8"))
    run = {
        "kind": "layout-vlm",
        "base_model": BASE_MODEL,
        "lora": {"r": 16, "alpha": 32, "targets": lora.target_modules},
        "epochs": args.epochs,
        "steps": step,
        "lr": args.lr,
        "max_side": args.max_side,
        "final_loss": round(sum(losses[-50:]) / max(1, len(losses[-50:])), 4),
        "dataset_hash": dataset["dataset_hash"],
        "layout_examples": len(examples),
        "git_sha": sha.strip(),
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
    }
    (out_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(json.dumps(run, indent=2))
    print(
        f"Push with: python -m ghost_training.push {out_dir} --kind layout-vlm --base {BASE_MODEL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
