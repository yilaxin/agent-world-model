#!/usr/bin/env bash
set -u

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round3_holdout logs
log="logs/round3_holdout_reactive_cells.log"
: > "$log"

# Reactive-only pass for the remaining/failed cells. The GPU server is
# currently offline, so world-model cells are deferred to the recovery pass.
for spec in "reddit reactive on" "gitlab reactive off" "gitlab reactive on" "shopping reactive off" "shopping reactive on"; do
  read -r site mode guard <<<"$spec"
  report="data/reports/webarena_p0_round3_holdout_${site}_${mode}_guard_${guard}.json"
  if [[ -f "$report" ]]; then
    echo "[$(date -u +%FT%TZ)] SKIP_EXISTING $site $mode $guard" >>"$log"
    continue
  fi
  echo "[$(date -u +%FT%TZ)] START $site $mode $guard" >>"$log"
  timeout 5400 bash scripts/run_webarena_p0_round3_cell.sh "$site" "$mode" "$guard" >>"$log" 2>&1
  rc=$?
  echo "[$(date -u +%FT%TZ)] DONE $site $mode $guard rc=$rc" >>"$log"
done
echo "[$(date -u +%FT%TZ)] REACTIVE_CELLS_DONE" >>"$log"
