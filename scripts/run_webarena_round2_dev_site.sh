#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 {gitlab|reddit|shopping} {reactive|world-model} [--detach]" >&2
  exit 64
fi
site="$1"
mode="$2"
detach="${3:-}"
case "$site" in
  gitlab) site_port=8023; ctrl_port=8022 ;;
  reddit) site_port=9999; ctrl_port=9998 ;;
  shopping) site_port=7770; ctrl_port=7771 ;;
  *) echo "unsupported site: $site" >&2; exit 64 ;;
esac
[[ "$mode" == "reactive" || "$mode" == "world-model" ]] || exit 64

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp/round2 data/trajectories_webarena_round2_dev data/reports
log="tmp/round2/${site}_${mode}.log"
config="${ROUND2_CONFIG:-configs/webarena_p0_round2_dev_${site}.json}"
report="${ROUND2_REPORT:-data/reports/webarena_p0_round2_dev_${site}_${mode}.json}"
output_dir="${ROUND2_OUTPUT_DIR:-data/trajectories_webarena_round2_dev/${site}/${mode}}"
if [[ "$detach" == "--detach" ]]; then
  nohup "$0" "$site" "$mode" >"$log" 2>&1 </dev/null &
  echo "ROUND2_DEV_STARTED site=$site mode=$mode log=$log"
  exit 0
fi

source .venv/bin/activate
export WA_GITLAB=http://localhost:8023
export WA_REDDIT=http://localhost:9999
export WA_SHOPPING=http://localhost:7770
export WA_SHOPPING_ADMIN=http://localhost:7780
export WA_WIKIPEDIA=http://localhost:8888
export WA_MAP=http://localhost:3000
export WA_HOMEPAGE=http://localhost:4399
export PYTHONSAFEPATH=1

cleanup() {
  webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
webarena-verified env start \
  --site "$site" --port "$site_port" --env-ctrl-port "$ctrl_port" --timeout 900

args=(
  python scripts/evaluate_webarena_online.py
  --config "$config"
  --mode "$mode"
  --navigation-guard on
  --output-dir "$output_dir"
  --report "$report"
)
if [[ "$mode" == "world-model" ]]; then
  remote_url="${ROUND2_REMOTE_URL:-http://localhost:18761}"
  args+=(--remote-agent-url "$remote_url")
fi
"${args[@]}"
echo "ROUND2_DEV_COMPLETE site=$site mode=$mode"
