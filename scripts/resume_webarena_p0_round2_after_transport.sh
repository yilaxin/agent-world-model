#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
transport_report="data/reports/webarena_p0_round2_holdout_reddit_world-model_guard_on_transport_recovery.json"
while [[ ! -f "$transport_report" ]]; do
  sleep 30
done
bash scripts/run_webarena_p0_round2_matrix.sh
bash scripts/run_webarena_p0_round2_recovery_matrix.sh
