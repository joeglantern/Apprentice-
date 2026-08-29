"""Turn a pulled export into a training PNG. PSDs are composited locally with psd-tools."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MAX_SIDE = 1024


def _fit(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def render_to_png(source: Path, target: Path) -> Path | None:
    """Returns the written PNG path, or None when the file cannot be rendered (.ai without
    a preview, corrupt file). Never raises on bad input; the caller logs and skips."""
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    try:
        if suffix == ".psd":
            from psd_tools import PSDImage

            composite = PSDImage.open(source).composite()
            if composite is None:
                return None
            _fit(composite).save(target, "PNG", optimize=True)
            return target
        if suffix in (".png", ".jpg", ".jpeg"):
            with Image.open(source) as img:
                _fit(img).save(target, "PNG", optimize=True)
            return target
        if suffix == ".ai":
            with Image.open(source) as img:  # needs Ghostscript; otherwise skipped
                _fit(img).save(target, "PNG", optimize=True)
            return target
    except Exception:  # noqa: BLE001
        return None
    return None
