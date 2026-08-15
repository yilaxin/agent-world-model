#!/usr/bin/env bash
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round3_holdout
status_file="tmp/round3_holdout/recovery_status.tsv"
touch "$status_file"

# Recovery re-runs every cell whose main-pass report is missing or incomplete.
# Each cell is wrapped in a process-level timeout so a wedged episode cannot
# stall the whole recovery pass.
for site in reddit gitlab shopping; do
  for spec in "reactive off" "reactive on" "world-model off" "world-model on"; do
    read -r mode guard <<<"$spec"
    report="data/reports/webarena_p0_round3_holdout_${site}_${mode}_guard_${guard}.json"
    if [[ -f "$report" ]]; then
      if .venv/bin/python - "$report" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
mode = "world-model" if p.get("world_model_agent_metrics") else "reactive"
rows = p.get("results", {}).get(mode, [])
expected = int(p.get("fixed_task_ids", []).__len__())
if p.get("failures") or len(rows) != expected:
    raise SystemExit(1)
print("CELL_ALREADY_COMPLETE", sys.argv[1])
PY
      then
        printf '%s\t%s\t%s\t%s\tSKIP_COMPLETE\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" >>"$status_file"
        continue
      fi
    fi
    printf '%s\t%s\t%s\t%s\tSTART\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" >>"$status_file"
    if timeout 5400 bash scripts/run_webarena_p0_round3_cell.sh "$site" "$mode" "$guard"; then
      rc=0
    else
      rc=$?
    fi
    printf '%s\t%s\t%s\t%s\tRC=%s\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" "$rc" >>"$status_file"
  done
done
printf '%s\tRECOVERY_MATRIX_PASS_COMPLETE\n' "$(date -u +%FT%TZ)" >>"$status_file"
