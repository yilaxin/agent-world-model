#!/usr/bin/env python3
"""Fail-fast CUDA and project-data preflight for the GPU server."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    card_path = PROJECT_ROOT / "data" / "phase2" / "dataset_card.json"
    card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.exists() else {}
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_runtime": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "device_count": torch.cuda.device_count(),
        "devices": [
            {
                "index": index,
                "name": torch.cuda.get_device_name(index),
                "capability": list(torch.cuda.get_device_capability(index)),
                "memory_gib": round(
                    torch.cuda.get_device_properties(index).total_memory / 1024**3, 2
                ),
            }
            for index in range(torch.cuda.device_count())
        ],
        "dataset_transitions": card.get("transition_count"),
        "p0_passed": card.get("quality_gates", {}).get("p0_500_transitions", False),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["cuda_available"]:
        print("CUDA preflight failed: install a CUDA-enabled PyTorch build.", file=sys.stderr)
        return 2
    if not report["p0_passed"]:
        print("Data preflight failed: phase-two P0 gate is not satisfied.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
