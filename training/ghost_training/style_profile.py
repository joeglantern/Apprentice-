"""Style profile (docs/06 D3): what the data says about the designer's habits.

Read by the creative director at generation time and by the designer himself.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from ghost_training.captions import orientation


def _alignment(bbox: dict[str, int], width: int) -> str:
    centre = bbox["x"] + bbox["width"] / 2
    if abs(centre - width / 2) < width * 0.04:
        return "center"
    return "left" if bbox["x"] < width / 2 else "right"


def build_style_profile(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    colours: Counter[str] = Counter()
    fonts: Counter[str] = Counter()
    orientations: Counter[str] = Counter()
    aligns: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    layer_counts: list[int] = []
    text_ratio: list[float] = []
    margins: list[float] = []
    type_sizes: list[float] = []
    headline_sizes: list[float] = []

    for payload in payloads:
        canvas = payload["file"]["canvas"]
        width, height = canvas.get("width", 0), canvas.get("height", 0)
        if not width or not height:
            continue
        orientations[orientation(width, height)] += 1
        formats[payload["file"].get("format", "?")] += 1
        colours.update(c.upper() for c in payload.get("palette", []))
        layers = [layer for layer in payload.get("layers", []) if layer.get("visible") is not False]
        layer_counts.append(len(layers))
        texts = [layer for layer in layers if layer.get("type") == "text"]
        text_ratio.append(len(texts) / len(layers) if layers else 0.0)
        sizes: list[float] = []
        for layer in texts:
            bbox = layer["bbox"]
            aligns[_alignment(bbox, width)] += 1
            typo = layer.get("typography") or {}
            if typo.get("font_family"):
                fonts[str(typo["font_family"])] += 1
            if typo.get("font_size"):
                size = float(typo["font_size"]) / width  # relative to canvas width
                sizes.append(size)
                type_sizes.append(size)
        if sizes:
            headline_sizes.append(max(sizes))
        # Margin: smallest distance from any non full-bleed layer to the canvas edge.
        edge: list[float] = []
        for layer in layers:
            bbox = layer["bbox"]
            if bbox["width"] >= width * 0.98 and bbox["height"] >= height * 0.98:
                continue
            edge.append(
                min(
                    bbox["x"] / width,
                    bbox["y"] / height,
                    (width - bbox["x"] - bbox["width"]) / width,
                    (height - bbox["y"] - bbox["height"]) / height,
                )
            )
        if edge:
            margins.append(max(0.0, min(edge)))

    def top(counter: Counter[str], n: int) -> list[dict[str, Any]]:
        total = sum(counter.values()) or 1
        return [{"value": k, "share": round(v / total, 3)} for k, v in counter.most_common(n)]

    return {
        "version": 1,
        "sample_size": len(payloads),
        "dominant_colours": top(colours, 12),
        "fonts": top(fonts, 8),
        "orientations": top(orientations, 3),
        "formats": top(formats, 4),
        "text_alignment": top(aligns, 3),
        "layers_per_design": {
            "median": median(layer_counts) if layer_counts else None,
            "min": min(layer_counts) if layer_counts else None,
            "max": max(layer_counts) if layer_counts else None,
        },
        "text_layer_share": round(median(text_ratio), 3) if text_ratio else None,
        "margin_ratio": round(median(margins), 3) if margins else None,
        "type_size_ratio": {
            "median": round(median(type_sizes), 4) if type_sizes else None,
            "headline_median": round(median(headline_sizes), 4) if headline_sizes else None,
        },
        "notes": [
            "Ratios are relative to canvas width (type sizes, margins) or height (margins).",
            "Derived only from records with consent.project_opted_in == true.",
        ],
    }
