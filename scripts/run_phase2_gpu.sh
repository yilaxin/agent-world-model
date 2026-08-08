#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python scripts/gpu_preflight.py
python scripts/train_phase2_world_model.py --device cuda
python scripts/evaluate_phase2_world_model.py --split validation --device cuda
python scripts/evaluate_phase2_world_model.py --split test --device cuda

echo "Phase-two CUDA training and validation completed."
