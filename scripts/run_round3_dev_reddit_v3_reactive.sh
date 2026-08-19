#!/usr/bin/env bash
set -u

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round3 logs
log="logs/round3_dev_reddit_v3_reactive.log"
: > "$log"

echo "[$(date -u +%FT%TZ)] START site=reddit" >>"$log"
ROUND2_CONFIG="configs/webarena_p0_round3_dev_reddit.json" \
ROUND2_REPORT="data/reports/webarena_p0_round3_dev_v3_reddit_reactive.json" \
ROUND2_OUTPUT_DIR="data/trajectories_webarena_round3_dev_v3/reddit/reactive" \
bash scripts/run_webarena_round2_dev_site.sh reddit reactive >>"$log" 2>&1
rc=$?
echo "[$(date -u +%FT%TZ)] DONE rc=$rc" >>"$log"
