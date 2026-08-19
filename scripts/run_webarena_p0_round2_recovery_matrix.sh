#!/usr/bin/env bash
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
source .venv/bin/activate
mkdir -p tmp/round2_holdout
status_file="tmp/round2_holdout/recovery_status.tsv"
touch "$status_file"

export WA_GITLAB=http://localhost:8023
export WA_REDDIT=http://localhost:9999
export WA_SHOPPING=http://localhost:7770
export WA_SHOPPING_ADMIN=http://localhost:7780
export WA_WIKIPEDIA=http://localhost:8888
export WA_MAP=http://localhost:3000
export WA_HOMEPAGE=http://localhost:4399
export PYTHONSAFEPATH=1

has_missing_key_failure() {
  python - "$1" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding="utf-8"))
raise SystemExit(0 if any("OPENAI_API_KEY" in str(x.get("error","")) for x in p.get("failures",[])) else 1)
PY
}

recovery_complete() {
  python - "$1" "$2" <<'PY'
import json,sys
recovery=json.load(open(sys.argv[1],encoding="utf-8"))
source=json.load(open(sys.argv[2],encoding="utf-8"))
expected=sum("OPENAI_API_KEY" in str(x.get("error","")) for x in source.get("failures",[]))
raise SystemExit(0 if not recovery.get("failures") and len(recovery.get("results",[])) == expected else 1)
PY
}

failure_source() {
  local site="$1" mode="$2" guard="$3"
  local main="data/reports/webarena_p0_round2_holdout_${site}_${mode}_guard_${guard}.json"
  local transport="data/reports/webarena_p0_round2_holdout_${site}_${mode}_guard_${guard}_transport_recovery.json"
  if [[ -f "$transport" ]] && has_missing_key_failure "$transport"; then
    printf '%s\n' "$transport"
  elif [[ -f "$main" ]] && has_missing_key_failure "$main"; then
    printf '%s\n' "$main"
  fi
}

for site in reddit gitlab shopping; do
  case "$site" in
    reddit) site_port=9999; ctrl_port=9998; ready_url=http://localhost:9999/login ;;
    gitlab) site_port=8023; ctrl_port=8022; ready_url=http://localhost:8023/users/sign_in ;;
    shopping) site_port=7770; ctrl_port=7771; ready_url=http://localhost:7770/customer/account/login ;;
  esac
  needs_site=0
  for spec in "reactive off" "reactive on" "world-model off" "world-model on"; do
    read -r mode guard <<<"$spec"
    source_report="$(failure_source "$site" "$mode" "$guard")"
    recovery="data/reports/webarena_p0_round2_recovery_${site}_${mode}_guard_${guard}.json"
    if [[ -n "$source_report" ]] && { [[ ! -f "$recovery" ]] || ! recovery_complete "$recovery" "$source_report"; }; then
      needs_site=1
    fi
  done
  if [[ "$needs_site" -eq 0 ]]; then
    printf '%s\t%s\tNO_RECOVERY_NEEDED\n' "$(date -u +%FT%TZ)" "$site" >>"$status_file"
    continue
  fi

  webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true
  webarena-verified env start --site "$site" --port "$site_port" --env-ctrl-port "$ctrl_port" --timeout 900
  if [[ "$site" == "gitlab" ]]; then
    for _ in $(seq 1 180); do
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' webarena_verified_gitlab 2>/dev/null || true)"
      [[ "$health" == "healthy" ]] && break
      sleep 2
    done
    [[ "$(docker inspect --format '{{.State.Health.Status}}' webarena_verified_gitlab)" == "healthy" ]]
  fi
  python - "$ready_url" <<'PY'
import sys,time,urllib.error,urllib.request
url=sys.argv[1]
for attempt in range(60):
    try:
        with urllib.request.urlopen(url,timeout=10) as response:
            if response.status < 500: break
    except urllib.error.HTTPError as error:
        if error.code < 500: break
        if attempt == 59: raise
    except Exception:
        if attempt == 59: raise
    time.sleep(2)
else:
    raise SystemExit("site did not become ready")
PY
  sleep 20

  for spec in "reactive off" "reactive on" "world-model off" "world-model on"; do
    read -r mode guard <<<"$spec"
    report="$(failure_source "$site" "$mode" "$guard")"
    recovery="data/reports/webarena_p0_round2_recovery_${site}_${mode}_guard_${guard}.json"
    if [[ -z "$report" ]]; then continue; fi
    if [[ -f "$recovery" ]] && recovery_complete "$recovery" "$report"; then
      printf '%s\t%s\t%s\t%s\tSKIP_EXISTING\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" >>"$status_file"
      continue
    fi
    if [[ -f "$recovery" ]]; then
      incomplete="${recovery%.json}.incomplete_$(date -u +%Y%m%dT%H%M%SZ).json"
      mv "$recovery" "$incomplete"
      printf '%s\t%s\t%s\t%s\tARCHIVE=%s\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" "$incomplete" >>"$status_file"
    fi
    extra_args=()
    if [[ "$report" == *_transport_recovery.json ]]; then
      extra_args+=(
        --failure-report "$report"
        --failure-config "configs/webarena_p0_round2_holdout_${site}_${mode}_guard_${guard}_transport_recovery.json"
      )
    fi
    printf '%s\t%s\t%s\t%s\tSTART\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" >>"$status_file"
    if python scripts/recover_webarena_p0_round2_fuzzy.py \
      --site "$site" --mode "$mode" --navigation-guard "$guard" \
      "${extra_args[@]}"; then
      rc=0
    else
      rc=$?
    fi
    printf '%s\t%s\t%s\t%s\tRC=%s\n' "$(date -u +%FT%TZ)" "$site" "$mode" "$guard" "$rc" >>"$status_file"
  done
  webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true
done

if python scripts/consolidate_webarena_p0_round2_reports.py; then
  consolidate_rc=0
else
  consolidate_rc=$?
fi
printf '%s\tCONSOLIDATE_RC=%s\n' "$(date -u +%FT%TZ)" "$consolidate_rc" >>"$status_file"

if [[ "$consolidate_rc" -eq 0 ]] && python scripts/analyze_webarena_p0_2x2.py \
  --manifest configs/webarena_p0_round2_holdout_frozen.json \
  --report-prefix webarena_p0_round2_consolidated \
  --site-config-template 'configs/webarena_p0_round2_holdout_{site}_frozen.json' \
  --trajectory-root data/trajectories_webarena_p0_round2_holdout \
  --output data/reports/webarena_p0_round2_2x2_analysis.json; then
  rc=0
else
  rc=$?
fi
printf '%s\tANALYSIS_RC=%s\n' "$(date -u +%FT%TZ)" "$rc" >>"$status_file"
