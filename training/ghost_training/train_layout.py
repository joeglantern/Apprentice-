"""QLoRA pretraining for the layout model (docs/06 D2, D14) on the Crello corpus.

Teaches Qwen2.5-VL-3B the serialize.py layout language: given a one-line brief
("Design a Poster for foodDrinks."), emit a `<canvas>/<shape>/<text>/<image>` layout.
This is the composition prior; the designer's own (much smaller) dataset fine-tunes on
top of it later, once collected. Runs on the Legion's 8GB card: 4-bit NF4 base, LoRA
r=16 on the attention and MLP projections, gradient checkpointing, paged 8-bit AdamW.

Usage (Legion, training venv with the [train] extras and a cu128 torch):
    GHOST_DATA_DIR=data python -m ghost_training.train_layout \
        --corpus data/pretrain/crello.jsonl --epochs 2

Checkpoints land in GHOST_DATA_DIR/checkpoints/layout-pretrain-v1/ ready for
ghost-push. VRAM note: close ComfyUI first; both do not fit at once (docs/06 D7's
sequential-sharing rule applies to training too).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from pathlib import Path
from typing import Any

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"

SYSTEM = (
    "You are a graphic design layout engine. Reply with only a layout: one element "
    "per line in the <canvas>/<shape>/<text>/<image> format, coordinates on a "
    "0-1000 grid normalised to the canvas width."
)

# A few phrasings so the model doesn't overfit one instruction string.
BRIEF_TEMPLATES = [
    "Design a {format} for {category}.",
    "Lay out a {format}. Subject: {category}.",
    "Compose a {category} {format}.",
]


def to_chat(example: dict[str, Any], rng: random.Random) -> dict[str, str]:
    """One corpus row -> a prompt/completion pair in chat form."""
    brief = rng.choice(BRIEF_TEMPLATES).format(
        format=example.get("format") or "design",
        category=example.get("category") or "general",
    )
    return {"brief": brief, "layout": example["layout"]}


def load_corpus(path: Path, seed: int = 7) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(to_chat(json.loads(line), rng))
    rng.shuffle(rows)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoProcessor,
        BitsAndBytesConfig,
        Qwen2_5_VLForConditionalGeneration,
        Trainer,
        TrainingArguments,
    )

    out_dir = args.out or (
        Path(os.environ.get("GHOST_DATA_DIR", "data")) / "checkpoints" / "layout-pretrain-v1"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_corpus(args.corpus)
    print(f"corpus: {len(rows)} layouts")

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    tokenizer = processor.tokenizer

    def tokenize(example: dict[str, str]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": example["brief"]},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        full = prompt + example["layout"] + tokenizer.eos_token
        enc = tokenizer(full, truncation=True, max_length=args.max_len)
        prompt_len = len(tokenizer(prompt)["input_ids"])
        labels = list(enc["input_ids"])
        labels[:prompt_len] = [-100] * min(prompt_len, len(labels))  # loss on the layout only
        enc["labels"] = labels
        return enc

    ds = Dataset.from_list(rows).map(tokenize, remove_columns=["brief", "layout"])

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID, quantization_config=bnb, device_map="auto"
    )
    model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    from transformers import DataCollatorForSeq2Seq

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(out_dir),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            # transformers 5 dropped warmup_ratio; this is the old 0.03 as steps.
            warmup_steps=max(
                1, round(0.03 * args.epochs * math.ceil(len(rows) / (args.batch * args.grad_accum)))
            ),
            logging_steps=10,
            save_strategy="steps",
            save_steps=50,
            save_total_limit=2,
            bf16=True,
            gradient_checkpointing=True,
            optim="paged_adamw_8bit",
            report_to=[],
        ),
        train_dataset=ds,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True),
    )
    # A killed run picks up from its newest mid-run checkpoint instead of step 0.
    # A power cut can truncate a checkpoint mid-save; only ones with a complete
    # trainer_state.json are resumable.
    last = max(
        (p for p in out_dir.glob("checkpoint-*") if (p / "trainer_state.json").is_file()),
        default=None,
        key=lambda p: int(p.name.split("-")[1]),
    )
    trainer.train(resume_from_checkpoint=str(last) if last else None)
    model.save_pretrained(out_dir / "final")
    tokenizer.save_pretrained(out_dir / "final")
    (out_dir / "run.json").write_text(
        json.dumps(
            {
                "base_model": MODEL_ID,
                "corpus": str(args.corpus),
                "layouts": len(rows),
                "epochs": args.epochs,
                "lora_r": 16,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("saved", out_dir / "final")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
