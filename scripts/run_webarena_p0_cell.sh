#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 {gitlab|reddit|shopping} {reactive|world-model} {on|off}" >&2
  exit 64
fi

site="$1"
mode="$2"
guard="$3"
case "$site" in
  gitlab) site_port=8023; ctrl_port=8022 ;;
  reddit) site_port=9999; ctrl_port=9998 ;;
  shopping) site_port=7770; ctrl_port=7771 ;;
  *) echo "unsupported site: $site" >&2; exit 64 ;;
esac
[[ "$mode" == "reactive" || "$mode" == "world-model" ]] || exit 64
[[ "$guard" == "on" || "$guard" == "off" ]] || exit 64
if [[ "$guard" == "on" ]]; then
  remote_port=18761
else
  remote_port=18760
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
source .venv/bin/activate
lock_dir="/tmp/webarena_p0_${site}.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "site already has an active P0 cell: $site" >&2
  exit 75
fi
release_lock() {
  rmdir "$lock_dir" >/dev/null 2>&1 || true
}
trap release_lock EXIT
export WA_GITLAB=http://localhost:8023
export WA_REDDIT=http://localhost:9999
export WA_SHOPPING=http://localhost:7770
export WA_SHOPPING_ADMIN=http://localhost:7780
export WA_WIKIPEDIA=http://localhost:8888
export WA_MAP=http://localhost:3000
export WA_HOMEPAGE=http://localhost:4399
export PYTHONSAFEPATH=1

python scripts/verify_webarena_p0_freeze.py
report="data/reports/webarena_p0_${site}_${mode}_guard_${guard}.json"
if [[ -f "$report" ]]; then
  if python - "$report" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding="utf-8"))
expected=len(p["fixed_task_ids"])*len(p["fixed_seeds"])
rows=p["results"].get("world-model" if "world_model_agent_metrics" in p and p["world_model_agent_metrics"] else "reactive",[])
if p.get("failures") or len(rows)!=expected:
    raise SystemExit(1)
print("CELL_ALREADY_COMPLETE",sys.argv[1])
PY
  then
    exit 0
  fi
  incomplete="${report%.json}.incomplete_$(date -u +%Y%m%dT%H%M%SZ).json"
  mv "$report" "$incomplete"
  echo "ARCHIVED_INCOMPLETE_REPORT $incomplete"
fi

cleanup() {
  webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true
}
cleanup_and_unlock() {
  cleanup
  release_lock
}
trap cleanup_and_unlock EXIT
cleanup
webarena-verified env start \
  --site "$site" \
  --port "$site_port" \
  --env-ctrl-port "$ctrl_port" \
  --timeout 900
python scripts/evaluate_webarena_online.py \
  --config "configs/webarena_p0_holdout_${site}_frozen.json" \
  --mode "$mode" \
  --navigation-guard "$guard" \
  --remote-agent-url "http://localhost:${remote_port}" \
  --output-dir "data/trajectories_webarena_p0/${site}/${mode}_guard_${guard}" \
  --report "$report"
cleanup
release_lock
trap - EXIT
echo "P0_CELL_COMPLETE site=$site mode=$mode guard=$guard"
