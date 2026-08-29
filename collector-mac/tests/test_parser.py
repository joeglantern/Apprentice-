from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ghost_agent.parser import (
    bbox_to_dict,
    dominant_palette,
    intersect,
    parse_design_file,
    rgb_to_hex,
)


def test_helpers() -> None:
    assert rgb_to_hex((26, 26, 26)) == "#1A1A1A"
    assert bbox_to_dict((120, 80, 760, 176)) == {"x": 120, "y": 80, "width": 640, "height": 96}
    a = {"x": 0, "y": 0, "width": 100, "height": 100}
    b = {"x": 50, "y": 50, "width": 100, "height": 100}
    assert intersect(a, b) == {"x": 50, "y": 50, "width": 50, "height": 50}
    assert intersect(a, {"x": 200, "y": 200, "width": 10, "height": 10})["width"] == 0


def test_dominant_palette_finds_flat_colours() -> None:
    img = Image.new("RGB", (100, 100), "#F2A623")
    img.paste("#1A1A1A", (0, 0, 50, 100))
    pal = dominant_palette(img)
    assert set(pal[:2]) == {"#F2A623", "#1A1A1A"}


def test_parse_png(tmp_path: Path) -> None:
    f = tmp_path / "hero.png"
    Image.new("RGB", (320, 180), "#3B8BD4").save(f, dpi=(144, 144))
    rec = parse_design_file(f)
    assert rec["file"] == {
        "original_name": "hero.png",
        "format": "png",
        "canvas": {"width": 320, "height": 180, "dpi": 144},
    }
    assert rec["layers"][0]["bbox"] == {"x": 0, "y": 0, "width": 320, "height": 180}
    assert rec["palette"][0] == "#3B8BD4"
    assert "consent" not in rec  # consent is attached by sync.py from real state, never here


def test_unsupported_extension(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("nope")
    with pytest.raises(ValueError):
        parse_design_file(f)


def test_psd_fixture_if_present() -> None:
    """Drop any real .psd into tests/fixtures/ to exercise the psd path locally."""
    fixtures = Path(__file__).parent / "fixtures"
    psds = list(fixtures.glob("*.psd")) if fixtures.exists() else []
    if not psds:
        pytest.skip("no PSD fixtures")
    rec = parse_design_file(psds[0])
    assert rec["file"]["format"] == "psd"
    assert rec["file"]["canvas"]["width"] > 0
    for i, layer in enumerate(rec["layers"]):
        assert layer["z_index"] == i
        assert layer["type"] in {"text", "shape", "image"}
        assert layer["bbox"]["width"] > 0 and layer["bbox"]["height"] > 0
