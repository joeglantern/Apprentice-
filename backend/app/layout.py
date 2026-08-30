"""Layout stage. Heuristic engine driven by the style profile until the layout VLM lands.

Turns a DesignPlan into the layer JSON the app renders (docs/01 section 3 shape). The
profile supplies the designer's habits: margin ratio, dominant alignment, headline size
relative to canvas width. The trained model will replace `heuristic_layout` with a call
to the Legion; the output contract stays the same.

The recipe is a poster, not a web hero (docs/06 D15): the image is full bleed, a scrim
darkens the text zone so type can sit on top of it legibly, and the type stack is
anchored to the bottom of that zone with a real hierarchy - small letter-spaced eyebrow,
one very large headline, subhead, details, a button. Landscape puts the zone on the
left, portrait on the bottom. A logo role becomes a small wordmark at the top.
"""

from __future__ import annotations

from typing import Any

from app.director import DEFAULT_PALETTE, DesignPlan, PlanElement

# Composition hints appended to every image prompt: the renderer is painting a poster
# background, so it must leave room for type and must not paint its own lettering.
IMAGE_PROMPT_SUFFIX = (
    "photorealistic poster background photograph, shot on a full frame camera, cinematic "
    "lighting, strong single subject, clean uncluttered negative space, no text, no "
    "letters, no logos, no watermark"
)

# Director typeface -> families the app bundles (app/assets/fonts, all OFL). Bebas is a
# condensed uppercase display face with one weight, so its headline scale runs larger.
FONT_PAIRINGS: dict[str, dict[str, Any]] = {
    "inter": {"display": "Inter", "body": "Inter", "display_weight": 800, "uppercase": False},
    "bebas": {"display": "Bebas Neue", "body": "Inter", "display_weight": 400, "uppercase": True},
    "playfair": {
        "display": "Playfair Display",
        "body": "Inter",
        "display_weight": 700,
        "uppercase": False,
    },
    "grotesk": {
        "display": "Space Grotesk",
        "body": "Space Grotesk",
        "display_weight": 700,
        "uppercase": False,
    },
}

# Poster headlines are big. A designer profile can push this up, never below the floor.
HEADLINE_RATIO_FLOOR = 0.075
HEADLINE_RATIO_DEFAULT = 0.085


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


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_colour: str) -> float:
    """DesignPlan validates palette_intent is #RRGGBB, but this stays defensive - a
    malformed colour must never crash the whole render, only degrade the contrast
    guess (treated as mid-grey rather than raising)."""
    try:
        r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    except (ValueError, IndexError):
        return 0.5
    r, g, b = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio, 1 (identical) to 21 (black on white)."""
    la, lb = _relative_luminance(a) + 0.05, _relative_luminance(b) + 0.05
    return max(la, lb) / min(la, lb)


def _readable_text_colour(candidate: str, background: str, min_ratio: float = 4.5) -> str:
    """The plan's palette colour if it reads clearly against the background, otherwise
    whichever of near-black/near-white actually contrasts - never silently unreadable
    text, which a director-picked palette can produce (e.g. two close warm tones)."""
    if _contrast_ratio(candidate, background) >= min_ratio:
        return candidate
    white_ratio = _contrast_ratio("#FFFFFF", background)
    black_ratio = _contrast_ratio("#111111", background)
    return "#FFFFFF" if white_ratio >= black_ratio else "#111111"


def _blend(colour: str, opacity: float, under: str = "#808080") -> str:
    """What a semi-transparent scrim looks like over an unknown photo, approximated as
    over mid-grey - the colour the text contrast is actually checked against."""
    try:
        top = [int(colour[i : i + 2], 16) for i in (1, 3, 5)]
        base = [int(under[i : i + 2], 16) for i in (1, 3, 5)]
    except (ValueError, IndexError):
        return under
    mixed = [round(t * opacity + b * (1 - opacity)) for t, b in zip(top, base, strict=True)]
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def _darkest(palette: list[str]) -> str:
    return min(palette, key=_relative_luminance)


def _brightest(palette: list[str]) -> str:
    return max(palette, key=_relative_luminance)


def _wordmark(content: str) -> str:
    text = content.strip()
    for suffix in (" logo", " wordmark", " brand mark"):
        if text.lower().endswith(suffix):
            text = text[: -len(suffix)]
    return text.strip().upper()


def heuristic_layout(plan: DesignPlan, profile: dict[str, Any] | None) -> dict[str, Any]:
    width, height = plan.canvas["width"], plan.canvas["height"]
    landscape = width >= height
    short_side = min(width, height)
    # Clamped so an unusual profile (e.g. mostly centred single-block designs, whose
    # min-edge margin skews high) can never push the text column negative.
    margin_ratio = min(
        max(float(_profile_value(profile, "margin_ratio", default=0.06)), 0.04), 0.12
    )
    margin = int(short_side * margin_ratio)
    align = _dominant(profile, "text_alignment", "left")
    profile_ratio = _profile_value(profile, "type_size_ratio", "headline_median", default=None)
    headline_ratio = (
        max(float(profile_ratio), HEADLINE_RATIO_FLOOR) if profile_ratio else HEADLINE_RATIO_DEFAULT
    )
    palette = plan.palette_intent or list(DEFAULT_PALETTE)
    scrim = _darkest(palette)
    accent = _brightest(palette) if len(palette) > 1 else "#FFFFFF"
    scrim_opacity = 0.78
    on_scrim = _blend(scrim, scrim_opacity)
    fg = _readable_text_colour("#FFFFFF", on_scrim)
    accent = _readable_text_colour(accent, on_scrim, min_ratio=3.0)

    ordered = sorted(plan.elements, key=lambda e: e.priority)
    layers: list[dict[str, Any]] = []

    def add(layer: dict[str, Any]) -> None:
        layer["layer_id"] = f"L{len(layers) + 1:02d}"
        layer["z_index"] = len(layers)
        layers.append(layer)

    # 1. Full-bleed image. Without one (director dropped it, validator would have
    #    refused) the darkest palette colour is the ground.
    images = [e for e in ordered if e.role == "image"]
    if images:
        image = images[0]
        base_prompt = (image.image_prompt or image.content).strip().rstrip(",. ")
        layer = {
            "name": image.content,
            "type": "image",
            "bbox": {"x": 0, "y": 0, "width": width, "height": height},
            "image_prompt": f"{base_prompt}, {IMAGE_PROMPT_SUFFIX}",
        }
        if image.scene_text:
            # Words inside the photo are the one case the "no text" suffix must not
            # apply to; the renderer switches to Flux for this layer (inference.py).
            layer["image_prompt"] = (
                f"{base_prompt}, poster background photograph, cinematic lighting"
            )
            layer["scene_text"] = image.scene_text.strip()[:40]
        add(layer)
    else:
        add(
            {
                "name": "background",
                "type": "shape",
                "bbox": {"x": 0, "y": 0, "width": width, "height": height},
                "color": {"hex": scrim, "opacity": 1.0},
            }
        )

    # 2. Text zone + scrim. Left ~55% on landscape, bottom ~58% on portrait.
    if landscape:
        zone = {"x": 0, "y": 0, "width": int(width * 0.56), "height": height}
    else:
        zone_h = int(height * 0.58)
        zone = {"x": 0, "y": height - zone_h, "width": width, "height": zone_h}
    add(
        {
            "name": "scrim",
            "type": "shape",
            "bbox": dict(zone),
            "color": {"hex": scrim, "opacity": scrim_opacity},
        }
    )
    # The layer schema has no gradients, so the scrim fades into the photo through a
    # run of thin bands of falling opacity past its edge instead of a hard cut.
    steps = 8
    fade = int((width if landscape else height) * 0.14)
    for i in range(steps):
        opacity = round(scrim_opacity * (1 - (i + 1) / (steps + 1)), 3)
        # Edges are cumulative rounded offsets so the bands tile exactly: no gap (a
        # light hairline) and no overlap (a dark one, doubled opacity).
        start, end = round(fade * i / steps), round(fade * (i + 1) / steps)
        if landscape:
            band = {"x": zone["width"] + start, "y": 0, "width": end - start, "height": height}
        else:
            band = {"x": 0, "y": zone["y"] - end, "width": width, "height": end - start}
        add(
            {
                "name": "scrim fade",
                "type": "shape",
                "bbox": band,
                "color": {"hex": scrim, "opacity": opacity},
            }
        )
    # A light full-canvas tint unifies the photo with the palette.
    add(
        {
            "name": "tint",
            "type": "shape",
            "bbox": {"x": 0, "y": 0, "width": width, "height": height},
            "color": {"hex": scrim, "opacity": 0.12},
        }
    )

    text_left = zone["x"] + margin
    text_width = zone["width"] - 2 * margin
    zone_bottom = zone["y"] + zone["height"] - margin
    # The designer's own dominant font wins once there is a profile; otherwise the
    # director's pairing from the bundled OFL set (app/assets/fonts).
    pairing = FONT_PAIRINGS.get(plan.typeface, FONT_PAIRINGS["inter"])
    profile_font = _dominant(profile, "fonts", "")
    display_family = profile_font or pairing["display"]
    body_family = profile_font or pairing["body"]
    display_weight = pairing["display_weight"]
    headline_upper = pairing["uppercase"]
    font_family = body_family

    def x_for(w: int) -> int:
        if align == "center":
            return text_left + (text_width - w) // 2
        if align == "right":
            return text_left + text_width - w
        return text_left

    # 3. Wordmark top-left, from a logo role if the director gave one.
    logos = [e for e in ordered if e.role == "logo"]
    if logos:
        size = _text_size("logo", width, headline_ratio)
        add(
            {
                "name": "wordmark",
                "type": "text",
                "bbox": {"x": margin, "y": margin, "width": text_width, "height": int(size * 1.3)},
                "text": _wordmark(logos[0].content),
                "align": "left",
                "typography": {
                    "font_family": font_family,
                    "font_size": size,
                    "font_weight": 700,
                    "letter_spacing": round(size * 0.18, 1),
                    "line_height": 1.2,
                },
                "color": {"hex": fg, "opacity": 1.0},
            }
        )

    # 4. The stack, laid out bottom-up so it anchors to the bottom of the zone:
    #    cta, body, subhead, headline, accent bar, eyebrow (caption).
    order = {"caption": 0, "headline": 1, "subhead": 2, "body": 3, "cta": 4}
    texts = sorted((e for e in ordered if e.role in order), key=lambda e: order[e.role])
    if not any(e.role == "headline" for e in texts):
        texts.insert(0, PlanElement(role="headline", content="Untitled", priority=1))
    blocks: list[dict[str, Any]] = []
    for element in texts:
        size = _text_size(element.role, width, headline_ratio)
        content = element.content.strip()
        if element.role in ("caption", "cta"):
            content = content.upper()
        if element.role == "headline" and headline_upper:
            content = content.upper()
        chars_per_line = max(1, int(text_width / max(1, size * 0.52)))
        max_lines = 3 if element.role == "headline" else 8
        # Explicit newlines (the director writes details one per line) count as lines.
        lines = sum(max(1, -(-len(p) // chars_per_line)) for p in content.split("\n"))
        lines = max(1, min(max_lines, lines))
        line_height = 1.02 if element.role == "headline" else 1.3
        h = int(size * line_height * lines)
        w = text_width
        layer: dict[str, Any] = {
            "name": element.role,
            "type": "text",
            "text": content,
            "align": align,
            "typography": {
                "font_family": display_family if element.role == "headline" else font_family,
                "font_size": size,
                "font_weight": {"headline": display_weight, "cta": 700, "caption": 600}.get(
                    element.role, 400
                ),
                "line_height": line_height,
            },
            "color": {"hex": accent if element.role == "caption" else fg, "opacity": 1.0},
        }
        if element.role == "caption":
            layer["typography"]["letter_spacing"] = round(size * 0.2, 1)
        if element.role == "cta":
            pad = int(size * 0.9)
            w = min(text_width, int(len(content) * size * 0.68) + 2 * pad)
            h += pad
            layer["typography"]["letter_spacing"] = round(size * 0.08, 1)
            layer["background"] = {"hex": accent, "opacity": 1.0}
            layer["color"] = {"hex": _readable_text_colour(scrim, accent), "opacity": 1.0}
        layer["bbox"] = {"x": x_for(w), "y": 0, "width": w, "height": h}
        blocks.append((layer, size))  # type: ignore[arg-type]

    # Gaps: tight between headline and its eyebrow, generous before the cta.
    y = zone_bottom
    placed: list[dict[str, Any]] = []
    for layer, size in reversed(blocks):  # type: ignore[misc]
        gap = {
            "cta": int(size * 1.4),
            "headline": int(size * 0.35),
            "caption": int(size * 0.9),
        }.get(layer["name"], int(size * 0.7))
        y -= layer["bbox"]["height"]
        if y < zone["y"] + margin:
            break
        layer["bbox"]["y"] = y
        placed.append(layer)
        if layer["name"] == "headline":
            bar_h = max(4, int(size * 0.08))
            y -= int(size * 0.45) + bar_h
            placed.append(
                {
                    "name": "accent bar",
                    "type": "shape",
                    "bbox": {
                        "x": x_for(int(size * 1.6)),
                        "y": y,
                        "width": int(size * 1.6),
                        "height": bar_h,
                    },
                    "color": {"hex": accent, "opacity": 1.0},
                }
            )
            y -= int(size * 0.35)
        else:
            y -= gap
    for layer in reversed(placed):
        add(layer)

    return {"canvas": {"width": width, "height": height}, "layers": layers}


def _text_size(role: str, width: int, headline_ratio: float) -> int:
    base = max(12, int(width * headline_ratio))
    scale = {
        "headline": 1.0,
        "subhead": 0.36,
        "body": 0.22,
        "caption": 0.17,
        "cta": 0.2,
        "logo": 0.18,
    }[role]
    return max(12, int(base * scale))
