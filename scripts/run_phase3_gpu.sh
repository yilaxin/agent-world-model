#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
CHECKPOINT="${PHASE2_CHECKPOINT:-artifacts/phase2/world_model_best.pt}"

"${PYTHON_BIN}" - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("Phase 3 GPU evaluation requires CUDA; refusing CPU fallback")
print({
    "torch": torch.__version__,
    "cuda": torch.version.cuda,
    "device": torch.cuda.get_device_name(0),
    "memory_gib": round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2),
})
PY

"${PYTHON_BIN}" scripts/evaluate_phase3_planner.py \
  --device cuda \
  --checkpoint "${CHECKPOINT}" \
  --output data/reports/phase3_evaluation_gpu.json

"${PYTHON_BIN}" scripts/evaluate_phase3_multistep.py \
  --device cuda \
  --checkpoint "${CHECKPOINT}" \
  --output data/reports/phase3_multistep_observed_gpu.json

"${PYTHON_BIN}" scripts/demo_phase3_agent.py \
  --device cuda \
  --checkpoint "${CHECKPOINT}" \
  --output data/reports/phase3_demo_gpu.json
