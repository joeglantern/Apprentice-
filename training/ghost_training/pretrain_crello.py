"""Maps the Crello dataset (docs/06 D14 - CDLA-Permissive-2.0, commercial use OK) onto
this project's doc 01 layer schema, then serialises it with ghost_training.serialize
into the same text format the layout model trains on (docs/06 D2's LayoutPrompter-style
grid). This is public, third-party design data - consent.project_opted_in never applies
to it, unlike pull.py/validate.py's designer data, so it deliberately does not import
anything from validate.py. Pretraining signal only: the designer's own (much smaller)
real data, once collected, is still the actual target style (docs/03 D14).

Never touches pixel data: the per-element previews are never read. They do still have
to be downloaded - they live inside the same parquet shards as the layout columns, so
streaming through `datasets` could not skip them and produced nothing in ten minutes on
the Legion's link. Shards are fetched whole (train is 31 x ~500 MB) into
GHOST_DATA_DIR/pretrain/crello_raw with `--download N`, then read column-wise with
pyarrow, which does skip the preview bytes.

The real shard schema differs from the dataset card: `type`, `font`, `text_align`,
`category` and `format` are integer class labels (names live in the parquet's embedded
Hugging Face metadata), boxes are absolute pixels, colours are `rgba(r, g, b, a)`
strings (one per element for shapes, one per character for text) and bold is a
per-character list. Everything here was checked against a downloaded shard, not docs.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ghost_training.serialize import serialize

# Crello element classes -> this project's three layer kinds (doc 01 section 3).
_TYPE_MAP = {
    "TextElement": "text",
    "ImageElement": "image",
    "SvgElement": "shape",
    "ColoredBackground": "shape",
    "SvgMaskElement": "shape",
}

# Columns actually needed; `preview` and `image` (the element previews) are never read.
CRELLO_COLUMNS = [
    "canvas_width",
    "canvas_height",
    "category",
    "format",
    "type",
    "left",
    "top",
    "width",
    "height",
    "opacity",
    "color",
    "text",
    "font",
    "font_size",
    "font_bold",
    "text_color",
    "text_align",
    "line_height",
    "letter_spacing",
]

_RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


class Labels:
    """Class-label names for the integer columns, read from the shard's own metadata."""

    def __init__(self, names: dict[str, list[str]]) -> None:
        self.names = names

    @classmethod
    def from_parquet(cls, path: Path) -> Labels:
        import pyarrow.parquet as pq

        meta = pq.ParquetFile(path).schema_arrow.metadata or {}
        info = json.loads(meta.get(b"huggingface", b"{}"))
        feats = info.get("info", {}).get("features", {})
        names: dict[str, list[str]] = {}
        for key in ("type", "font", "text_align", "category", "format"):
            feat = feats.get(key, {})
            feat = feat.get("feature", feat)  # list<ClassLabel> vs ClassLabel
            names[key] = list(feat.get("names") or [])
        return cls(names)

    def name(self, column: str, index: Any) -> str:
        try:
            return self.names[column][int(index)]
        except (KeyError, ValueError, IndexError, TypeError):
            return ""


def _hex(rgba: Any) -> str | None:
    """`rgba(230, 231, 232, 1)` -> `#E6E7E8`; None (never raises) on anything else."""
    m = _RGBA.match(str(rgba or ""))
    if not m:
        return None
    r, g, b = (int(v) for v in m.groups())
    if not all(0 <= c <= 255 for c in (r, g, b)):
        return None
    return f"#{r:02X}{g:02X}{b:02X}"


def crello_row_to_payload(row: dict[str, Any], labels: Labels) -> dict[str, Any] | None:
    """One Crello example -> a doc 01 section 3 payload (file.canvas + layers), or
    None if the row is too malformed or empty to be worth training on."""
    width, height = row.get("canvas_width"), row.get("canvas_height")
    if not width or not height or width <= 0 or height <= 0:
        return None

    def col(name: str) -> list[Any]:
        return list(row.get(name) or [])

    types, lefts, tops = col("type"), col("left"), col("top")
    widths, heights, opacities = col("width"), col("height"), col("opacity")
    colors, texts, fonts = col("color"), col("text"), col("font")
    sizes, bolds, text_colors = col("font_size"), col("font_bold"), col("text_color")
    aligns, line_heights, spacings = col("text_align"), col("line_height"), col("letter_spacing")

    def at(seq: list[Any], i: int, default: Any = None) -> Any:
        return seq[i] if i < len(seq) else default

    layers: list[dict[str, Any]] = []
    for i, raw_type in enumerate(types):
        kind = _TYPE_MAP.get(labels.name("type", raw_type))
        if kind is None:
            continue
        w, h = int(round(float(at(widths, i, 0)))), int(round(float(at(heights, i, 0))))
        if w <= 0 or h <= 0:
            continue
        layer: dict[str, Any] = {
            "layer_id": f"L{len(layers) + 1:02d}",
            "type": kind,
            "z_index": len(layers),
            "bbox": {
                "x": int(round(float(at(lefts, i, 0)))),
                "y": int(round(float(at(tops, i, 0)))),
                "width": w,
                "height": h,
            },
        }
        opacity = round(max(0.0, min(1.0, float(at(opacities, i, 1.0)))), 3)

        if kind == "text":
            content = str(at(texts, i, "")).strip()
            if not content:
                continue  # an empty text box teaches the model nothing
            layer["text"] = content
            typo: dict[str, Any] = {}
            size = at(sizes, i)
            if size:
                typo["font_size"] = int(round(float(size)))
            font = labels.name("font", at(fonts, i))
            if font:
                typo["font_family"] = font
            bold = at(bolds, i) or []
            typo["font_weight"] = (
                700 if bold and sum(bool(b) for b in bold) * 2 >= len(bold) else 400
            )
            lh = at(line_heights, i)
            if lh:
                typo["line_height"] = round(float(lh), 2)
            ls = at(spacings, i)
            if ls:
                typo["letter_spacing"] = round(float(ls), 2)
            layer["typography"] = typo
            align = labels.name("text_align", at(aligns, i))
            if align in ("left", "center", "right"):
                layer["align"] = align
            hex_colour = _hex((at(text_colors, i) or [None])[0])
        else:
            hex_colour = _hex((at(colors, i) or [None])[0])
        if hex_colour:
            layer["color"] = {"hex": hex_colour, "opacity": opacity}
        layers.append(layer)

    if len(layers) < 2:  # nothing resembling an actual composition
        return None
    return {
        "file": {
            "format": labels.name("format", row.get("format")) or "crello",
            "canvas": {"width": int(width), "height": int(height)},
        },
        "layers": layers,
    }


SHARD_URL = "https://huggingface.co/datasets/cyberagent/crello/resolve/main/data/{name}"
TRAIN_SHARDS = 31


def shard_name(i: int) -> str:
    return f"train-{i:05d}-of-{TRAIN_SHARDS:05d}.parquet"


def download_shards(raw_dir: Path, count: int) -> list[Path]:
    """Fetches the first `count` train shards that aren't already present. Each is
    ~500 MB; check disk before asking for all 31 (docs/06 D14)."""
    import httpx

    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(count):
        path = raw_dir / shard_name(i)
        if not path.exists():
            with httpx.stream("GET", SHARD_URL.format(name=path.name), follow_redirects=True) as r:
                r.raise_for_status()
                tmp = path.with_suffix(".part")
                with tmp.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
                tmp.rename(path)
        paths.append(path)
    return paths


def iter_serialized_examples(
    shards: list[Path], limit: int | None = None
) -> Iterator[dict[str, str]]:
    """Reads only CRELLO_COLUMNS from each shard (pyarrow skips the preview bytes) and
    yields {"category", "format", "layout"} rows in the exact text format serialize.py
    defines. category/format are the conditioning text for pretraining."""
    import pyarrow.parquet as pq

    seen = 0
    for shard in shards:
        labels = Labels.from_parquet(shard)
        table = pq.read_table(shard, columns=CRELLO_COLUMNS)
        for row in table.to_pylist():
            payload = crello_row_to_payload(row, labels)
            if payload is None:
                continue
            yield {
                "category": labels.name("category", row.get("category")) or "design",
                "format": payload["file"]["format"],
                "layout": serialize(payload),
            }
            seen += 1
            if limit is not None and seen >= limit:
                return


def main() -> int:
    """python -m ghost_training.pretrain_crello [--download N] [--limit M]"""
    import sys

    args = sys.argv[1:]
    download = int(args[args.index("--download") + 1]) if "--download" in args else 0
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    base = Path(os.environ.get("GHOST_DATA_DIR", "data")) / "pretrain"
    raw_dir = base / "crello_raw"
    shards = download_shards(raw_dir, download) if download else sorted(raw_dir.glob("*.parquet"))
    if not shards:
        print("no shards; pass --download N", file=sys.stderr)
        return 2
    out_path = base / "crello.jsonl"
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for example in iter_serialized_examples(shards, limit=limit):
            f.write(json.dumps(example) + "\n")
            count += 1
    print(json.dumps({"shards": len(shards), "written": count, "path": str(out_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
