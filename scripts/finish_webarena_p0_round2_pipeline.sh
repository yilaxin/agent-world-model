#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
status_file="tmp/round2_holdout/matrix_status.tsv"
while ! grep -q 'MATRIX_MAIN_PASS_COMPLETE' "$status_file" 2>/dev/null; do
  sleep 30
done
exec bash scripts/run_webarena_p0_round2_recovery_matrix.sh
