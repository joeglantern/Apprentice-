"""Style profile from the assets already in the database.

The training machine produces a richer profile alongside each checkpoint; until one has
been pushed, the director and the layout engine use this direct summary of the records.
Only records whose stored consent block is opted in are counted.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Asset


def _orientation(width: int, height: int) -> str:
    ratio = width / height if height else 1
    return "landscape" if ratio > 1.1 else "portrait" if ratio < 0.9 else "square"


def build_profile(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    colours: Counter[str] = Counter()
    fonts: Counter[str] = Counter()
    aligns: Counter[str] = Counter()
    orientations: Counter[str] = Counter()
    margins: list[float] = []
    headline: list[float] = []
    counts: list[int] = []
    for payload in payloads:
        canvas = payload.get("file", {}).get("canvas", {})
        width, height = canvas.get("width", 0), canvas.get("height", 0)
        if not width or not height:
            continue
        orientations[_orientation(width, height)] += 1
        colours.update(c.upper() for c in payload.get("palette", []))
        layers = [x for x in payload.get("layers", []) if x.get("visible") is not False]
        counts.append(len(layers))
        sizes: list[float] = []
        edges: list[float] = []
        for layer in layers:
            bbox = layer.get("bbox") or {}
            if not bbox:
                continue
            if layer.get("type") == "text":
                centre = bbox["x"] + bbox["width"] / 2
                if abs(centre - width / 2) < width * 0.04:
                    aligns["center"] += 1
                else:
                    aligns["left" if bbox["x"] < width / 2 else "right"] += 1
                typo = layer.get("typography") or {}
                if typo.get("font_family"):
                    fonts[str(typo["font_family"])] += 1
                if typo.get("font_size"):
                    sizes.append(float(typo["font_size"]) / width)
            if bbox["width"] >= width * 0.98 and bbox["height"] >= height * 0.98:
                continue
            edges.append(
                max(
                    0.0,
                    min(
                        bbox["x"] / width,
                        bbox["y"] / height,
                        (width - bbox["x"] - bbox["width"]) / width,
                        (height - bbox["y"] - bbox["height"]) / height,
                    ),
                )
            )
        if sizes:
            headline.append(max(sizes))
        if edges:
            margins.append(min(edges))

    def top(counter: Counter[str], n: int) -> list[dict[str, Any]]:
        total = sum(counter.values()) or 1
        return [{"value": k, "share": round(v / total, 3)} for k, v in counter.most_common(n)]

    return {
        "version": 1,
        "source": "backend-assets",
        "sample_size": len(payloads),
        "dominant_colours": top(colours, 12),
        "fonts": top(fonts, 8),
        "orientations": top(orientations, 3),
        "text_alignment": top(aligns, 3),
        "layers_per_design": {"median": median(counts) if counts else None},
        "margin_ratio": round(median(margins), 3) if margins else None,
        "type_size_ratio": {"headline_median": round(median(headline), 4) if headline else None},
    }


async def profile_from_db(session: AsyncSession, limit: int = 500) -> dict[str, Any]:
    stmt = select(Asset).where(Asset.status == "tagged").limit(limit)
    assets = (await session.exec(stmt)).all()
    payloads = [
        a.payload for a in assets if (a.payload.get("consent") or {}).get("project_opted_in")
    ]
    return build_profile(payloads)
