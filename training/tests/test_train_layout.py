from __future__ import annotations

import json
import random

from ghost_training.train_layout import BRIEF_TEMPLATES, load_corpus, to_chat


def test_to_chat_formats_a_brief_and_keeps_the_layout() -> None:
    rng = random.Random(1)
    row = {"category": "foodDrinks", "format": "Poster", "layout": "<canvas w=1000 h=1250>"}
    chat = to_chat(row, rng)
    assert "foodDrinks" in chat["brief"] and "Poster" in chat["brief"]
    assert chat["layout"] == "<canvas w=1000 h=1250>"
    assert any(t.split("{")[0].strip() and chat["brief"] for t in BRIEF_TEMPLATES)


def test_load_corpus_reads_and_shuffles(tmp_path) -> None:  # noqa: ANN001
    p = tmp_path / "c.jsonl"
    rows = [
        {"category": f"c{i}", "format": "Poster", "layout": f"<canvas w=1000 h={i}>"}
        for i in range(20)
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = load_corpus(p)
    assert len(out) == 20
    assert {r["layout"] for r in out} == {r["layout"] for r in rows}
    assert [r["layout"] for r in out] != [r["layout"] for r in rows]  # shuffled
