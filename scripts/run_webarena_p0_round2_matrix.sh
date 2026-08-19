#!/usr/bin/env bash
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round2_holdout
status_file="tmp/round2_holdout/matrix_status.tsv"
touch "$status_file"

# A pre-existing report is immutable evidence.  Incomplete reports are filled
# by the separate evaluator-initialization recovery pass, never by rerunning
# already judged holdout episodes.
for site in reddit gitlab shopping; do
  for spec in "reactive off" "reactive on" "world-model off" "world-model on"; do
    read -r mode guard <<<"$spec"
    report="data/reports/webarena_p0_round2_holdout_${site}_${mode}_guard_${guard}.json"
    if [[ -f "$report" ]]; then
      printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" "SKIP_EXISTING" >>"$status_file"
      continue
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" "START" >>"$status_file"
    if bash scripts/run_webarena_p0_round2_cell.sh "$site" "$mode" "$guard"; then
      rc=0
    else
      rc=$?
    fi
    printf '%s\t%s\t%s\t%s\tRC=%s\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" "$rc" >>"$status_file"
  done
done
printf '%s\tMATRIX_MAIN_PASS_COMPLETE\n' "$(date -u +%FT%TZ)" >>"$status_file"
