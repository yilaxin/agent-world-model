#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${MINIWOB_URL:?MINIWOB_URL must be configured before collection}"

python scripts/collect_phase2_counterfactuals.py \
  --seeds 40 \
  --seed-offset 3000 \
  --tasks-config configs/phase2_collection_expansion.json \
  --strategies hard_wrong_target,wrong_action_type,missing_target \
  --output-dir data/trajectories_phase2_counterfactual_p2 \
  --report data/reports/phase2_counterfactual_collection_p2.json

python scripts/build_phase2_dataset.py \
  data/trajectories_phase2 \
  data/trajectories_phase2_risk \
  data/trajectories_phase2_counterfactual \
  data/trajectories_phase2_expansion \
  data/trajectories_phase2_expansion_b \
  data/trajectories_phase2_expansion_c \
  data/trajectories_phase2_counterfactual_p2 \
  --output-dir data/phase2_p2 \
  --require-p0 \
  --require-counterfactual-p0

python scripts/train_phase2_multiseed.py \
  --config configs/phase2_world_model_multiseed_p2.json \
  --device cuda

python scripts/evaluate_counterfactual_ranking.py \
  --ensemble-manifest artifacts/phase2/world_model_ensemble_p2.json \
  --dataset-dir data/phase2_p2 \
  --device cuda \
  --minimum-informative-test-pairs 200 \
  --output data/reports/phase3_counterfactual_ranking_p2_gpu.json

