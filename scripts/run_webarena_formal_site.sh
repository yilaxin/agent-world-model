#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 {gitlab|reddit|shopping}" >&2
  exit 64
fi

site="$1"
case "$site" in
  gitlab)
    site_port=8023
    ctrl_port=8022
    ;;
  reddit)
    site_port=9999
    ctrl_port=9998
    ;;
  shopping)
    site_port=7770
    ctrl_port=7771
    ;;
  *)
    echo "unsupported site: $site" >&2
    exit 64
    ;;
esac

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
source .venv/bin/activate

# BrowserGym expands all WebArena placeholders while importing its task set,
# although this partition executes only the selected site's tasks.
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

for mode in reactive world-model; do
  cleanup
  webarena-verified env start \
    --site "$site" \
    --port "$site_port" \
    --env-ctrl-port "$ctrl_port" \
    --timeout 900
  python scripts/evaluate_webarena_online.py \
    --config "configs/webarena_formal_${site}.json" \
    --mode "$mode" \
    --remote-agent-url http://localhost:18765 \
    --output-dir "data/trajectories_webarena_formal/${site}/${mode}" \
    --report "data/reports/webarena_formal_${site}_${mode}.json"
  cleanup
done

trap - EXIT
echo "FORMAL_SITE_COMPLETE site=$site"
