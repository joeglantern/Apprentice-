"""Extract the doc 01 §3 metadata record from a design file.

Runs on the designer's Mac so the file itself is parsed locally. Produces the `file`,
`layers`, and `palette` blocks; `consent` and identity fields are attached by `sync.py`
from real agent state, never invented here.

See `.claude/skills/psd-metadata-extraction/SKILL.md` for the edge-case list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

PALETTE_MAX = 8
PALETTE_SAMPLE_PX = 256


# -- helpers -----------------------------------------------------------------


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def bbox_to_dict(bbox: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = bbox
    return {"x": int(left), "y": int(top), "width": int(right - left), "height": int(bottom - top)}


def intersect(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["width"], b["x"] + b["width"])
    y2 = min(a["y"] + a["height"], b["y"] + b["height"])
    return {"x": x1, "y": y1, "width": max(0, x2 - x1), "height": max(0, y2 - y1)}


def dominant_palette(image: Image.Image, max_colors: int = PALETTE_MAX) -> list[str]:
    """Dominant colours of an image, downsampled first so huge files stay cheap."""
    img = image.convert("RGB")
    img.thumbnail((PALETTE_SAMPLE_PX, PALETTE_SAMPLE_PX))
    quant = img.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    raw_palette = quant.getpalette() or []
    counts = sorted(quant.getcolors() or [], reverse=True)
    result: list[str] = []
    for _count, idx in counts:
        rgb = tuple(raw_palette[idx * 3 : idx * 3 + 3])
        if len(rgb) == 3:
            hx = rgb_to_hex(rgb)  # type: ignore[arg-type]
            if hx not in result:
                result.append(hx)
    return result[:max_colors]


# -- raster (png/jpg) ---------------------------------------------------------


def parse_raster(path: Path) -> dict[str, Any]:
    with Image.open(path) as img:
        width, height = img.size
        dpi = int(round(img.info.get("dpi", (72, 72))[0])) if img.info.get("dpi") else 72
        palette = dominant_palette(img)
    return {
        "file": {
            "original_name": path.name,
            "format": path.suffix.lower().lstrip("."),
            "canvas": {"width": width, "height": height, "dpi": dpi},
        },
        "layers": [
            {
                "layer_id": "L01",
                "name": path.stem,
                "type": "image",
                "z_index": 0,
                "visible": True,
                "bbox": {"x": 0, "y": 0, "width": width, "height": height},
            }
        ],
        "palette": palette,
    }


# -- psd ---------------------------------------------------------------------


def _layer_type(layer: Any) -> str | None:
    kind = getattr(layer, "kind", "")
    if kind == "type":
        return "text"
    if kind in {"shape", "solidcolorfill", "gradientfill", "patternfill"}:
        return "shape"
    if kind in {"pixel", "smartobject", "psdimage"}:
        return "image"
    # adjustment layers and anything else without geometry
    return None


def _typography(layer: Any) -> dict[str, Any] | None:
    """Best-effort typography; every lookup is guarded because engine data is often partial."""
    try:
        engine = layer.engine_dict
        style = engine["StyleRun"]["RunArray"][0]["StyleSheet"]["StyleSheetData"]
        resource = layer.resource_dict
        font_idx = int(style.get("Font", 0))
        fonts = resource["FontSet"]
        family = str(fonts[font_idx]["Name"]).strip("'") if font_idx < len(fonts) else None
        size = float(style.get("FontSize", 0)) or None
        tracking = style.get("Tracking")
        leading = style.get("Leading")
        weight = 700 if style.get("FauxBold") else 400
        if family and ("Bold" in family or "Black" in family or "Heavy" in family):
            weight = 700
        out: dict[str, Any] = {"font_family": family, "font_size": size, "font_weight": weight}
        if tracking is not None:
            out["letter_spacing"] = float(tracking) / 1000.0
        if leading is not None and size:
            out["line_height"] = round(float(leading) / size, 3)
        return out
    except Exception:  # noqa: BLE001 - psd engine data is genuinely unpredictable
        return None


def _solid_color(layer: Any) -> str | None:
    try:
        from psd_tools.constants import Tag

        setting = layer.tagged_blocks.get_data(Tag.SOLID_COLOR_SHEET_SETTING)
        if setting is None:
            return None
        color = setting[b"Clr "]
        rgb = (int(round(color[b"Rd  "])), int(round(color[b"Grn "])), int(round(color[b"Bl  "])))
        return rgb_to_hex(rgb)
    except Exception:  # noqa: BLE001
        return None


def _text_color(layer: Any) -> str | None:
    try:
        style = layer.engine_dict["StyleRun"]["RunArray"][0]["StyleSheet"]["StyleSheetData"]
        values = style["FillColor"]["Values"]  # ARGB floats 0..1
        rgb = tuple(int(round(v * 255)) for v in values[1:4])
        return rgb_to_hex(rgb)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return None


def _layer_color(layer: Any, ltype: str) -> dict[str, Any] | None:
    hex_value: str | None = None
    if ltype == "shape":
        hex_value = _solid_color(layer)
    elif ltype == "text":
        hex_value = _text_color(layer)
    if hex_value is None and ltype == "image":
        try:
            composite = layer.composite()
            if composite is not None:
                pal = dominant_palette(composite, 1)
                hex_value = pal[0] if pal else None
        except Exception:  # noqa: BLE001
            hex_value = None
    if hex_value is None:
        return None
    opacity = round(float(getattr(layer, "opacity", 255)) / 255.0, 3)
    return {"hex": hex_value, "opacity": opacity}


def parse_psd(path: Path) -> dict[str, Any]:
    from psd_tools import PSDImage

    psd = PSDImage.open(path)
    width, height = psd.width, psd.height
    canvas_box = {"x": 0, "y": 0, "width": width, "height": height}

    layers: list[dict[str, Any]] = []
    z = 0
    clip_base_bbox: dict[str, int] | None = None

    def walk(group: Any, prefix: str) -> None:
        nonlocal z, clip_base_bbox
        # psd-tools iterates bottom->top, which matches z_index ascending.
        for layer in group:
            name = f"{prefix}{layer.name}"
            if layer.is_group():
                walk(layer, f"{name}/")
                continue
            ltype = _layer_type(layer)
            if ltype is None:
                continue
            bbox = bbox_to_dict(layer.bbox)
            if bbox["width"] <= 0 or bbox["height"] <= 0:
                continue
            bbox = intersect(bbox, canvas_box)
            if getattr(layer, "clipping_layer", False) and clip_base_bbox is not None:
                bbox = intersect(bbox, clip_base_bbox)
            else:
                clip_base_bbox = bbox
            if bbox["width"] <= 0 or bbox["height"] <= 0:
                continue
            entry: dict[str, Any] = {
                "layer_id": f"L{len(layers) + 1:02d}",
                "name": name,
                "type": ltype,
                "z_index": z,
                "visible": bool(layer.is_visible()),
                "bbox": bbox,
            }
            if ltype == "text":
                typo = _typography(layer)
                if typo:
                    entry["typography"] = typo
                text = getattr(layer, "text", None)
                if text:
                    entry["text"] = str(text)[:500]
            color = _layer_color(layer, ltype)
            if color:
                entry["color"] = color
            layers.append(entry)
            z += 1

    walk(psd, "")

    palette: list[str] = []
    try:
        composite = psd.composite()
        if composite is not None:
            palette = dominant_palette(composite)
    except Exception:  # noqa: BLE001
        palette = []

    dpi = 72
    try:
        from psd_tools.constants import Resource

        res = psd.image_resources.get_data(Resource.RESOLUTION_INFO)
        if res is not None:
            dpi = int(round(res.horizontal))
    except Exception:  # noqa: BLE001
        pass

    return {
        "file": {
            "original_name": path.name,
            "format": "psd",
            "canvas": {"width": width, "height": height, "dpi": dpi},
        },
        "layers": layers,
        "palette": palette,
    }


# -- ai ----------------------------------------------------------------------


def parse_ai(path: Path) -> dict[str, Any]:
    """Modern .ai files are PDF-compatible. We record file-level info only for now;
    layer/OCG extraction is a follow-up (see skill edge cases). Palette comes from the
    embedded PDF preview when Pillow can read it, else stays empty."""
    palette: list[str] = []
    width = height = 0
    try:
        with Image.open(path) as img:  # works only if Ghostscript is available
            width, height = img.size
            palette = dominant_palette(img)
    except Exception:  # noqa: BLE001
        pass
    return {
        "file": {
            "original_name": path.name,
            "format": "ai",
            "canvas": {"width": width, "height": height, "dpi": 72},
        },
        "layers": [],
        "palette": palette,
    }


# -- entry point ---------------------------------------------------------------


def parse_design_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".psd":
        return parse_psd(p)
    if suffix == ".ai":
        return parse_ai(p)
    if suffix in {".png", ".jpg", ".jpeg"}:
        return parse_raster(p)
    raise ValueError(f"Unsupported design file type: {suffix}")
