"""Schema and consent validation for pulled records. Second line of consent defence."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

LAYER_TYPES = {"text", "shape", "image"}


def validate_record(record: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means the record may be used for training."""
    problems: list[str] = []
    payload = record.get("payload", record)

    consent = payload.get("consent")
    if not isinstance(consent, dict) or consent.get("project_opted_in") is not True:
        # This is the one check that must never be relaxed.
        problems.append("consent.project_opted_in is not true")

    for key in ("asset_id", "source_project", "captured_at", "file"):
        if key not in payload:
            problems.append(f"missing {key}")
    canvas = (payload.get("file") or {}).get("canvas") or {}
    if not (canvas.get("width", 0) > 0 and canvas.get("height", 0) > 0):
        problems.append("canvas has no size")

    layers = payload.get("layers", [])
    if not isinstance(layers, list):
        problems.append("layers is not a list")
        layers = []
    for i, layer in enumerate(layers):
        bbox = layer.get("bbox") or {}
        if layer.get("type") not in LAYER_TYPES:
            problems.append(f"layer {i} has unknown type {layer.get('type')!r}")
        if not all(k in bbox for k in ("x", "y", "width", "height")):
            problems.append(f"layer {i} has an incomplete bbox")
        elif bbox["width"] <= 0 or bbox["height"] <= 0:
            problems.append(f"layer {i} has a zero area bbox")

    for colour in payload.get("palette", []):
        if not (isinstance(colour, str) and len(colour) == 7 and colour[0] == "#"):
            problems.append(f"bad palette entry {colour!r}")
            break
    return problems


def is_consented(record: dict[str, Any]) -> bool:
    payload = record.get("payload", record)
    consent = payload.get("consent")
    return isinstance(consent, dict) and consent.get("project_opted_in") is True


def validate_dir(records_dir: Path) -> tuple[int, int, list[tuple[str, list[str]]]]:
    ok = bad = 0
    failures: list[tuple[str, list[str]]] = []
    for path in sorted(records_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            bad += 1
            failures.append((path.name, ["not valid json"]))
            continue
        problems = validate_record(record)
        if problems:
            bad += 1
            failures.append((path.name, problems))
        else:
            ok += 1
    return ok, bad, failures


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m ghost_training.validate <records dir>", file=sys.stderr)
        return 2
    ok, bad, failures = validate_dir(Path(args[0]))
    for name, problems in failures:
        print(f"{name}: {'; '.join(problems)}")
    print(f"{ok} valid, {bad} rejected")
    return 0 if ok and not any("consent" in p for _, ps in failures for p in ps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
