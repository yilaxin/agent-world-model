#!/usr/bin/env bash
# Run the W1 baseline working set (reactive only, no GPU required).
#
# The working set is deliberately small so a full pass fits inside one working
# day: GitLab 23 tasks x 3 seeds and Shopping 17 tasks x 3 seeds.  Each site is
# evaluated sequentially because the runner starts and stops its own site
# container.
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p tmp logs

log="${W1_LOG:-logs/w1_workingset_run.log}"
: >>"$log"

# A single-flight lock keeps two passes from fighting over the site containers.
lock="/tmp/w1_workingset.lock"

if [[ "${W1_DETACH:-}" == "--detach" ]]; then
  if ! mkdir "$lock" 2>/dev/null; then
    echo "W1_WORKINGSET_ALREADY_RUNNING lock=$lock"
    exit 75
  fi
  # Clear W1_DETACH for the child, otherwise it re-enters this branch and forks
  # a new process on every generation.
  W1_DETACH= nohup "$0" >>"$log" 2>&1 </dev/null &
  echo "W1_WORKINGSET_STARTED log=$log pid=$!"
  exit 0
fi

if [[ ! -d "$lock" ]]; then
  mkdir -p "$lock"
fi
trap 'rmdir "$lock" >/dev/null 2>&1 || true' EXIT

for site in gitlab shopping; do
  config="configs/webarena_w1_workingset_${site}.json"
  if [[ ! -f "$config" ]]; then
    echo "[$(date -u +%FT%TZ)] MISSING_CONFIG $config" >>"$log"
    exit 66
  fi
  echo "[$(date -u +%FT%TZ)] START site=$site config=$config" >>"$log"
  ROUND2_CONFIG="$config" \
  ROUND2_REPORT="data/reports/webarena_w1_workingset_${site}_reactive.json" \
  ROUND2_OUTPUT_DIR="data/trajectories_webarena_w1_workingset/${site}/reactive" \
  bash scripts/run_webarena_round2_dev_site.sh "$site" reactive >>"$log" 2>&1
  rc=$?
  echo "[$(date -u +%FT%TZ)] DONE site=$site rc=$rc" >>"$log"
  if [[ "$rc" -ne 0 ]]; then
    echo "[$(date -u +%FT%TZ)] ABORT after site=$site" >>"$log"
    exit "$rc"
  fi
done
echo "[$(date -u +%FT%TZ)] ALL_DONE" >>"$log"
