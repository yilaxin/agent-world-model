#!/usr/bin/env bash
set -u

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round3 logs
log="logs/round3_dev_reactive_run.log"
: > "$log"

for site in reddit gitlab shopping; do
  echo "[$(date -u +%FT%TZ)] START site=$site" >>"$log"
  ROUND2_CONFIG="configs/webarena_p0_round3_dev_${site}.json" \
  ROUND2_REPORT="data/reports/webarena_p0_round3_dev_${site}_reactive.json" \
  ROUND2_OUTPUT_DIR="data/trajectories_webarena_round3_dev/${site}/reactive" \
  bash scripts/run_webarena_round2_dev_site.sh "$site" reactive >>"$log" 2>&1
  rc=$?
  echo "[$(date -u +%FT%TZ)] DONE site=$site rc=$rc" >>"$log"
done
echo "[$(date -u +%FT%TZ)] ALL_DONE" >>"$log"
