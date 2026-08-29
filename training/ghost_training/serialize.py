"""Layout <-> text serialisation in the LayoutPrompter style (docs/06 D2).

The layout model reads and writes plain text, one element per line, on a 0..1000 grid
normalised to the canvas width so the same habits transfer across canvas sizes:

    <canvas w=1000 h=562>
    <text id=L01 x=75 y=50 w=400 h=60 size=40 weight=700 align=left>
    <shape id=L02 x=0 y=0 w=1000 h=562 fill=#F2A623>
    <image id=L03 x=520 y=80 w=430 h=400>

`serialize` produces this from a doc 01 record; `parse` turns model output back into the
JSON the app's canvas renders. Both are exact inverses on the grid.
"""

from __future__ import annotations

import re
from typing import Any

GRID = 1000
_LINE = re.compile(r"^<(?P<kind>canvas|text|shape|image)(?P<attrs>(?:\s+[a-z_]+=[^\s>]+)*)\s*>$")
_ATTR = re.compile(r"([a-z_]+)=([^\s>]+)")


def _scale(value: float, width: int) -> int:
    return int(round(value * GRID / width))


def _unscale(value: int, width: int) -> int:
    return int(round(value * width / GRID))


def _alignment(bbox: dict[str, int], width: int) -> str:
    centre = bbox["x"] + bbox["width"] / 2
    if abs(centre - width / 2) < width * 0.04:
        return "center"
    return "left" if bbox["x"] < width / 2 else "right"


def serialize(payload: dict[str, Any]) -> str:
    canvas = payload["file"]["canvas"]
    width, height = int(canvas["width"]), int(canvas["height"])
    lines = [f"<canvas w={GRID} h={_scale(height, width)}>"]
    layers = sorted(payload.get("layers", []), key=lambda layer: layer.get("z_index", 0))
    for layer in layers:
        if layer.get("visible") is False:
            continue
        bbox = layer["bbox"]
        attrs = {
            "id": layer.get("layer_id", "L00"),
            "x": _scale(bbox["x"], width),
            "y": _scale(bbox["y"], width),
            "w": _scale(bbox["width"], width),
            "h": _scale(bbox["height"], width),
        }
        kind = layer.get("type", "image")
        if kind == "text":
            typo = layer.get("typography") or {}
            if typo.get("font_size"):
                attrs["size"] = _scale(float(typo["font_size"]), width)
            if typo.get("font_weight"):
                attrs["weight"] = int(typo["font_weight"])
            attrs["align"] = _alignment(bbox, width)
        if kind in ("shape", "text") and (layer.get("color") or {}).get("hex"):
            attrs["fill"] = layer["color"]["hex"].upper()
        rendered = " ".join(f"{k}={v}" for k, v in attrs.items())
        lines.append(f"<{kind} {rendered}>")
    return "\n".join(lines)


def parse(text: str, canvas_width: int) -> dict[str, Any]:
    """Parse model output back into {canvas, layers}. Unknown or malformed lines are skipped."""
    layers: list[dict[str, Any]] = []
    height = canvas_width
    z = 0
    for raw in text.strip().splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        kind = m.group("kind")
        attrs = dict(_ATTR.findall(m.group("attrs")))
        if kind == "canvas":
            try:
                height = _unscale(int(attrs.get("h", GRID)), canvas_width)
            except ValueError:
                pass
            continue
        try:
            bbox = {
                "x": _unscale(int(attrs["x"]), canvas_width),
                "y": _unscale(int(attrs["y"]), canvas_width),
                "width": _unscale(int(attrs["w"]), canvas_width),
                "height": _unscale(int(attrs["h"]), canvas_width),
            }
        except (KeyError, ValueError):
            continue
        if bbox["width"] <= 0 or bbox["height"] <= 0:
            continue
        layer: dict[str, Any] = {
            "layer_id": attrs.get("id", f"L{z + 1:02d}"),
            "type": kind,
            "z_index": z,
            "bbox": bbox,
        }
        if kind == "text":
            typo: dict[str, Any] = {}
            if "size" in attrs and attrs["size"].isdigit():
                typo["font_size"] = _unscale(int(attrs["size"]), canvas_width)
            if "weight" in attrs and attrs["weight"].isdigit():
                typo["font_weight"] = int(attrs["weight"])
            if typo:
                layer["typography"] = typo
            if attrs.get("align") in ("left", "center", "right"):
                layer["align"] = attrs["align"]
        fill = attrs.get("fill", "")
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", fill):
            layer["color"] = {"hex": fill.upper(), "opacity": 1.0}
        layers.append(layer)
        z += 1
    return {"canvas": {"width": canvas_width, "height": height}, "layers": layers}
