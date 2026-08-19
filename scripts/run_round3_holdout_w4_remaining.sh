#!/usr/bin/env bash
set -u

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round3_holdout logs
log="logs/round3_holdout_w4_remaining.log"
: > "$log"

for spec in "reddit world-model off" "reddit world-model on" "shopping world-model off" "shopping world-model on"; do
  read -r site mode guard <<<"$spec"
  report="data/reports/webarena_p0_round3_holdout_${site}_${mode}_guard_${guard}.json"
  if [[ -f "$report" ]]; then
    if .venv/bin/python - "$report" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
mode = "world-model" if p.get("world_model_agent_metrics") else "reactive"
rows = p.get("results", {}).get(mode, [])
if p.get("failures") or not rows:
    raise SystemExit(1)
print("CELL_ALREADY_COMPLETE", sys.argv[1])
PY
    then
      echo "[$(date -u +%FT%TZ)] SKIP_COMPLETE $site $mode $guard" >>"$log"
      continue
    fi
  fi
  echo "[$(date -u +%FT%TZ)] START $site $mode $guard" >>"$log"
  timeout 5400 bash scripts/run_webarena_p0_round3_cell.sh "$site" "$mode" "$guard" >>"$log" 2>&1
  rc=$?
  echo "[$(date -u +%FT%TZ)] DONE $site $mode $guard rc=$rc" >>"$log"
done
echo "[$(date -u +%FT%TZ)] W4_REMAINING_DONE" >>"$log"
