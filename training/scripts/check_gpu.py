"""Confirm the GPU before any run. Exits non-zero if it is not the expected 8 GB card."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import torch
    except ImportError:
        print("torch is not installed; install the [train] extra on the Legion", file=sys.stderr)
        return 2
    if not torch.cuda.is_available():
        print("CUDA is not available", file=sys.stderr)
        return 1
    name = torch.cuda.get_device_name(0)
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"{name}: {total_gb:.1f} GB, torch {torch.__version__}, cuda {torch.version.cuda}")
    if total_gb < 7.5:
        print("less than the expected 8 GB; do not start a training run", file=sys.stderr)
        return 1
    if total_gb > 9:
        print("more memory than planned for; configs are sized for 8 GB and will still work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
