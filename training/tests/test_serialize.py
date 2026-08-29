from __future__ import annotations

from ghost_training.serialize import parse, serialize
from tests.conftest import payload


def test_serialize_format() -> None:
    text = serialize(payload())
    lines = text.splitlines()
    assert lines[0] == "<canvas w=1000 h=562>"
    assert lines[1] == "<shape id=L01 x=0 y=0 w=1000 h=562 fill=#F2A623>"
    assert lines[2].startswith("<text id=L02 x=75 y=50 w=400 h=60 size=40 weight=700 align=left")
    assert lines[3] == "<image id=L03 x=520 y=80 w=400 h=400>"


def test_round_trip_is_close_on_the_grid() -> None:
    p = payload()
    parsed = parse(serialize(p), canvas_width=1600)
    assert parsed["canvas"] == {"width": 1600, "height": 899}
    assert [layer["type"] for layer in parsed["layers"]] == ["shape", "text", "image"]
    head = parsed["layers"][1]
    assert head["bbox"] == {"x": 120, "y": 80, "width": 640, "height": 96}
    assert head["typography"] == {"font_size": 64, "font_weight": 700}
    assert head["align"] == "left"
    assert parsed["layers"][0]["color"]["hex"] == "#F2A623"


def test_hidden_layers_are_skipped_and_order_follows_z() -> None:
    p = payload()
    p["layers"][2]["visible"] = False
    p["layers"][0]["z_index"] = 5  # background moved to the top
    text = serialize(p)
    assert "<image" not in text
    assert text.splitlines()[-1].startswith("<shape")


def test_parse_ignores_garbage() -> None:
    text = "\n".join(
        [
            "hello",
            "<canvas w=1000 h=500>",
            "<text id=A x=1 y=2 w=0 h=5>",
            "<image x=10 y=10 w=100 h=100>",
            "<bogus x=1>",
        ]
    )
    out = parse(text, 800)
    assert out["canvas"]["height"] == 400
    assert len(out["layers"]) == 1
    assert out["layers"][0]["bbox"] == {"x": 8, "y": 8, "width": 80, "height": 80}
