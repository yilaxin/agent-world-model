#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 {gitlab|reddit|shopping}" >&2
  exit 64
fi
site="$1"
case "$site" in
  gitlab) site_port=8023; ctrl_port=8022 ;;
  reddit) site_port=9999; ctrl_port=9998 ;;
  shopping) site_port=7770; ctrl_port=7771 ;;
  *) echo "unsupported site: $site" >&2; exit 64 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
source .venv/bin/activate
lock_dir="/tmp/webarena_p0_${site}.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "site already has an active P0 cell: $site" >&2
  exit 75
fi
cleanup() {
  webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true
  rmdir "$lock_dir" >/dev/null 2>&1 || true
}
trap cleanup EXIT

export WA_GITLAB=http://localhost:8023
export WA_REDDIT=http://localhost:9999
export WA_SHOPPING=http://localhost:7770
export WA_SHOPPING_ADMIN=http://localhost:7780
export WA_WIKIPEDIA=http://localhost:8888
export WA_MAP=http://localhost:3000
export WA_HOMEPAGE=http://localhost:4399
export PYTHONSAFEPATH=1
unset OPENAI_API_KEY || true

python scripts/verify_webarena_p0_freeze.py
for mode in reactive world-model; do
  for guard in off on; do
    if [[ "$guard" == "on" ]]; then remote_port=18761; else remote_port=18760; fi
    webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true
    webarena-verified env start \
      --site "$site" --port "$site_port" --env-ctrl-port "$ctrl_port" --timeout 900
    python scripts/recover_webarena_p0_fuzzy_episodes.py \
      --site "$site" --mode "$mode" --navigation-guard "$guard" \
      --remote-agent-url "http://localhost:${remote_port}"
  done
done
echo "P0_RECOVERY_SITE_COMPLETE site=$site"
