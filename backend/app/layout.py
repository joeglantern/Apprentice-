"""Layout stage. Heuristic engine driven by the style profile until the layout VLM lands.

Turns a DesignPlan into the layer JSON the app renders (docs/01 section 3 shape). The
profile supplies the designer's habits: margin ratio, dominant alignment, headline size
relative to canvas width. The trained model will replace `heuristic_layout` with a call
to the Legion; the output contract stays the same.
"""

from __future__ import annotations

from typing import Any

from app.director import DesignPlan, PlanElement


def _profile_value(profile: dict[str, Any] | None, *keys: str, default: Any) -> Any:
    node: Any = profile or {}
    for key in keys:
        if not isinstance(node, dict) or key not in node or node[key] is None:
            return default
        node = node[key]
    return node


def _dominant(profile: dict[str, Any] | None, key: str, default: str) -> str:
    entries = _profile_value(profile, key, default=[])
    return entries[0]["value"] if entries else default


def heuristic_layout(plan: DesignPlan, profile: dict[str, Any] | None) -> dict[str, Any]:
    width, height = plan.canvas["width"], plan.canvas["height"]
    # Clamped so an unusual profile (e.g. mostly centred single-block designs, whose
    # min-edge margin skews high) can never push the landscape text column negative.
    margin_ratio = min(max(float(_profile_value(profile, "margin_ratio", default=0.06)), 0.0), 0.15)
    margin = int(width * margin_ratio)
    align = _dominant(profile, "text_alignment", "left")
    headline_ratio = float(
        _profile_value(profile, "type_size_ratio", "headline_median", default=0.05)
    )
    palette = plan.palette_intent or ["#1A1A1A", "#F2A623", "#FFFFFF"]
    fg = palette[0]
    bg = palette[1] if len(palette) > 1 else "#FFFFFF"
    accent = palette[2] if len(palette) > 2 else fg

    ordered = sorted(plan.elements, key=lambda e: e.priority)
    layers: list[dict[str, Any]] = []
    z = 0

    def add(layer: dict[str, Any]) -> None:
        nonlocal z
        layer["layer_id"] = f"L{len(layers) + 1:02d}"
        layer["z_index"] = z
        layers.append(layer)
        z += 1

    # Background: any shape element becomes the full-bleed ground.
    shapes = [e for e in ordered if e.role == "shape"]
    add(
        {
            "name": shapes[0].content if shapes else "background",
            "type": "shape",
            "bbox": {"x": 0, "y": 0, "width": width, "height": height},
            "color": {"hex": bg, "opacity": 1.0},
        }
    )

    # Image: right column on landscape, top band on portrait.
    images = [e for e in ordered if e.role == "image"]
    landscape = width >= height
    text_left = margin
    text_width = width - 2 * margin
    text_top = margin
    if images:
        image = images[0]
        if landscape:
            img_w = int(width * 0.46)
            bbox = {
                "x": width - margin - img_w,
                "y": margin,
                "width": img_w,
                "height": height - 2 * margin,
            }
            text_width = width - 3 * margin - img_w
        else:
            img_h = int(height * 0.48)
            bbox = {"x": margin, "y": margin, "width": width - 2 * margin, "height": img_h}
            text_top = margin * 2 + img_h
        add(
            {
                "name": image.content,
                "type": "image",
                "bbox": bbox,
                "image_prompt": image.image_prompt or image.content,
            }
        )

    # Text stack: headline, subhead, body, caption, cta, top to bottom.
    order = {"headline": 0, "subhead": 1, "body": 2, "caption": 3, "cta": 4, "logo": 5}
    texts = sorted((e for e in ordered if e.role in order), key=lambda e: order[e.role])
    font_family = _dominant(profile, "fonts", "Helvetica Neue")
    y = text_top
    for element in texts:
        size = _text_size(element, width, headline_ratio)
        chars_per_line = max(1, int(text_width / max(1, size * 0.55)))
        lines = max(1, min(4, -(-len(element.content) // chars_per_line)))
        h = int(size * 1.15 * lines)
        w = text_width
        if element.role == "cta":
            pad = int(size * 0.6)
            w = min(w, size * 9)
            h += pad
        # Only a narrower box (the cta) actually moves with alignment; full-width text
        # boxes carry `align` for the renderer's text-anchor and don't need to shift.
        if align == "center":
            x = text_left + (text_width - w) // 2
        elif align == "right":
            x = text_left + text_width - w
        else:
            x = text_left
        layer: dict[str, Any] = {
            "name": element.role,
            "type": "text",
            "bbox": {"x": x, "y": y, "width": w, "height": h},
            "text": element.content,
            "align": align,
            "typography": {
                "font_family": font_family,
                "font_size": size,
                "font_weight": 700 if element.role in ("headline", "cta") else 400,
                "line_height": 1.15,
            },
            "color": {"hex": accent if element.role == "cta" else fg, "opacity": 1.0},
        }
        if element.role == "cta":
            layer["background"] = {"hex": accent, "opacity": 1.0}
            layer["color"] = {"hex": bg, "opacity": 1.0}
        add(layer)
        y += h + int(size * 0.8)
        if y > height - margin:
            break

    return {"canvas": {"width": width, "height": height}, "layers": layers}


def _text_size(element: PlanElement, width: int, headline_ratio: float) -> int:
    base = max(12, int(width * headline_ratio))
    scale = {
        "headline": 1.0,
        "subhead": 0.5,
        "body": 0.34,
        "caption": 0.26,
        "cta": 0.4,
        "logo": 0.4,
    }[element.role]
    return max(12, int(base * scale))
