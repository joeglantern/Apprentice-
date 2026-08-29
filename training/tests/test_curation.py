from __future__ import annotations

import json

from ghost_training.captions import caption
from ghost_training.config import TrainingConfig
from ghost_training.prepare import prepare
from ghost_training.style_profile import build_style_profile
from ghost_training.validate import is_consented, validate_record
from tests.conftest import payload, record, write_raw


def test_validate_accepts_good_record() -> None:
    assert validate_record(record(payload())) == []


def test_validate_rejects_missing_or_false_consent() -> None:
    p = payload()
    p["consent"]["project_opted_in"] = False
    assert "consent.project_opted_in is not true" in validate_record(record(p))
    del p["consent"]
    assert "consent.project_opted_in is not true" in validate_record(record(p))
    assert not is_consented(record(p))
    p["consent"] = {"project_opted_in": "true"}  # a string is not True
    assert not is_consented(record(p))


def test_validate_flags_schema_problems() -> None:
    p = payload()
    p["layers"][0]["bbox"]["width"] = 0
    p["layers"][1]["type"] = "video"
    p["palette"].append("red")
    problems = validate_record(record(p))
    assert any("zero area" in x for x in problems)
    assert any("unknown type" in x for x in problems)
    assert any("palette" in x for x in problems)


def test_caption() -> None:
    text = caption(payload())
    assert text.startswith("ghoststyle, landscape graphic design")
    assert "with typography" in text and "with photographic elements" in text
    assert "palette #1A1A1A #F2A623 #3B8BD4 #FFFFFF" in text
    assert "layered composition" in text


def test_style_profile() -> None:
    profile = build_style_profile([payload(), payload()])
    assert profile["sample_size"] == 2
    assert profile["dominant_colours"][0]["value"] in {"#1A1A1A", "#F2A623", "#3B8BD4", "#FFFFFF"}
    assert profile["fonts"][0]["value"] == "Neue Haas Grotesk"
    assert profile["orientations"][0]["value"] == "landscape"
    assert profile["text_alignment"][0]["value"] == "left"
    assert profile["layers_per_design"]["median"] == 3
    assert 0 < profile["margin_ratio"] < 0.2
    assert profile["type_size_ratio"]["headline_median"] == 0.04


def test_prepare_builds_sets_and_drops_unconsented(cfg: TrainingConfig) -> None:
    good = record(payload())
    bad_payload = payload()
    bad_payload["consent"]["project_opted_in"] = False
    bad = record(bad_payload)
    write_raw(cfg, [good, bad])

    summary = prepare(cfg)
    assert summary["style_images"] == 1
    assert summary["layout_examples"] == 1
    assert [r["asset_id"] for r in summary["rejected"]] == [bad["asset_id"]]

    style = cfg.curated_dir / "style" / "10_ghoststyle"
    assert (style / f"{good['asset_id']}.png").exists()
    assert (style / f"{good['asset_id']}.txt").read_text().startswith("ghoststyle")
    assert not (style / f"{bad['asset_id']}.png").exists()

    rows = [
        json.loads(x) for x in (cfg.curated_dir / "layout/train.jsonl").read_text().splitlines()
    ]
    assert rows[0]["canvas_width"] == 1600
    assert rows[0]["text"].startswith("<canvas w=1000 h=562>")
    profile = json.loads((cfg.curated_dir / "style_profile.json").read_text())
    assert profile["sample_size"] == 1
    assert json.loads((cfg.curated_dir / "dataset.json").read_text())["dataset_hash"]


def test_prepare_skips_missing_file(cfg: TrainingConfig) -> None:
    write_raw(cfg, [record(payload())], with_files=False)
    summary = prepare(cfg)
    assert summary["style_images"] == 0
    assert summary["rejected"][0]["problems"] == ["export file missing"]
