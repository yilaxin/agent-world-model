#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

"${PYTHON_BIN}" - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("The formal phase-2/3 improvement run requires CUDA")
print({
    "torch": torch.__version__,
    "cuda": torch.version.cuda,
    "device": torch.cuda.get_device_name(0),
})
PY

if [[ "${PHASE23_SKIP_OBSERVED_COLLECTION:-0}" == "1" ]]; then
  echo "[phase23] Reusing completed multistep and terminal-failure collections."
else
  "${PYTHON_BIN}" scripts/collect_phase2_trajectories.py \
    --config configs/phase2_collection_multistep.json \
    --output-dir data/trajectories_phase2_multistep \
    --report data/reports/phase2_multistep_collection.json

  "${PYTHON_BIN}" scripts/collect_phase2_trajectories.py \
    --config configs/phase2_collection_terminal_failures.json \
    --output-dir data/trajectories_phase2_terminal_failures \
    --report data/reports/phase2_terminal_failure_collection.json
fi

"${PYTHON_BIN}" scripts/collect_phase2_counterfactuals_parallel.py \
  --tasks-config configs/phase2_collection.json \
  --seeds 40 \
  --seed-offset 1000 \
  --strategies hard_wrong_target,wrong_action_type,missing_target \
  --workers "${PHASE23_COUNTERFACTUAL_WORKERS:-4}" \
  --output-dir data/trajectories_phase2_counterfactual_p2 \
  --report data/reports/phase2_counterfactual_collection_p2.json

if [[ -n "${REDDIT:-}" ]]; then
  "${PYTHON_BIN}" scripts/collect_phase2_counterfactuals.py \
    --tasks-config configs/webarena_counterfactual_eval.json \
    --seeds 1 \
    --seed-offset 0 \
    --strategies hard_wrong_target,wrong_action_type,missing_target \
    --output-dir data/trajectories_webarena_counterfactual \
    --report data/reports/webarena_counterfactual_collection.json
else
  echo "[phase23] REDDIT is not configured; skipping live WebArena counterfactual collection."
  echo "[phase23] This run does not claim WebArena online-success improvement."
fi

"${PYTHON_BIN}" scripts/export_human_review_queue.py \
  data/trajectories \
  data/trajectories_phase2 \
  data/trajectories_phase2_expansion \
  data/trajectories_phase2_expansion_b \
  data/trajectories_phase2_expansion_c \
  data/trajectories_phase2_risk \
  data/trajectories_phase2_multistep \
  data/trajectories_phase2_terminal_failures \
  data/trajectories_phase2_counterfactual_p2 \
  data/trajectories_webarena_counterfactual \
  --limit 500 \
  --output data/human_review/phase2_review_queue.csv \
  --report data/reports/phase2_human_review_queue.json

"${PYTHON_BIN}" scripts/build_phase2_dataset.py \
  data/trajectories \
  data/trajectories_phase2 \
  data/trajectories_phase2_expansion \
  data/trajectories_phase2_expansion_b \
  data/trajectories_phase2_expansion_c \
  data/trajectories_phase2_risk \
  data/trajectories_phase2_multistep \
  data/trajectories_phase2_terminal_failures \
  data/trajectories_phase2_counterfactual_p2 \
  data/trajectories_webarena_counterfactual \
  --output-dir data/phase2_p2 \
  --require-p0 \
  --require-counterfactual-p0 \
  --require-multistep-p1

"${PYTHON_BIN}" scripts/train_phase2_multiseed.py \
  --config configs/phase2_world_model_multiseed_p2.json \
  --device cuda

"${PYTHON_BIN}" scripts/evaluate_counterfactual_ranking.py \
  --dataset-dir data/phase2_p2 \
  --ensemble-manifest artifacts/phase2/world_model_ensemble_p2.json \
  --device cuda \
  --output data/reports/phase3_counterfactual_ranking_p2_gpu.json

"${PYTHON_BIN}" scripts/evaluate_phase3_multistep.py \
  --dataset-dir data/phase2_p2 \
  --ensemble-manifest artifacts/phase2/world_model_ensemble_p2.json \
  --device cuda \
  --output data/reports/phase3_multistep_observed_p2_gpu.json
