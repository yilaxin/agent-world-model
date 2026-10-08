#!/usr/bin/env bash
# Round-4 WebArena world-model evaluation queue.
#
# Runs the four world-model cells sequentially (GitLab/Shopping x guard on/off),
# retries a cell when it fails, and aborts a cell whose browser environment
# stalls: a stall is detected when no new trajectory file appears for
# ROUND4_STALL_SECONDS (default 20 minutes).
set -uo pipefail

repo="${ROUND4_REPO:-/home/filp/agent_world_model}"
cd "$repo" || exit 1
mkdir -p tmp

lock=/tmp/round4_queue.lock
if ! mkdir "$lock" 2>/dev/null; then
  echo "round4 queue already running" >&2
  exit 75
fi
trap 'rmdir "$lock" >/dev/null 2>&1 || true' EXIT

stall_seconds="${ROUND4_STALL_SECONDS:-1200}"
attempts="${ROUND4_CELL_ATTEMPTS:-3}"

log() { echo "$(date -u +%FT%TZ) $*"; }

health() {
  curl -fsS --max-time 6 http://127.0.0.1:18760/health >/dev/null 2>&1 &&
    curl -fsS --max-time 6 http://127.0.0.1:18761/health >/dev/null 2>&1
}

kill_cell_eval() {
  pkill -f "evaluate_webarena_online.py --config configs/webarena_p0_round4_holdout_$1" >/dev/null 2>&1
  sleep 15
  pkill -9 -f "evaluate_webarena_online.py --config configs/webarena_p0_round4_holdout_$1" >/dev/null 2>&1
}

log "QUEUE_START pid=$$"
for cell in "gitlab world-model off" "gitlab world-model on" "shopping world-model off" "shopping world-model on"; do
  set -- $cell
  site=$1; mode=$2; guard=$3
  dir="data/trajectories_webarena_p0_round4_holdout/$site/${mode}_guard_$guard"
  log "CELL_START $site $mode $guard"
  ok=0
  attempt=1
  while [ "$attempt" -le "$attempts" ]; do
    for _ in $(seq 1 30); do health && break; log "WAITING_FOR_TUNNEL $site $mode $guard"; sleep 20; done
    if ! health; then log "TUNNEL_DOWN $site $mode $guard"; break; fi
    bash scripts/run_webarena_p0_round4_cell.sh "$site" "$mode" "$guard" >>tmp/round4_queue_cell.log 2>&1 &
    cpid=$!
    last=$(find "$dir" -name '*.jsonl' 2>/dev/null | wc -l)
    changed=$(date +%s)
    while kill -0 "$cpid" 2>/dev/null; do
      sleep 60
      cur=$(find "$dir" -name '*.jsonl' 2>/dev/null | wc -l)
      if [ "$cur" != "$last" ]; then last=$cur; changed=$(date +%s); fi
      if [ $(( $(date +%s) - changed )) -gt "$stall_seconds" ]; then
        log "STALL_DETECTED $site $mode $guard episodes=$cur"
        kill_cell_eval "$site"
        changed=$(date +%s)
        break
      fi
    done
    wait "$cpid"; rc=$?
    if [ "$rc" -eq 0 ]; then ok=1; log "CELL_OK $site $mode $guard"; break; fi
    log "CELL_FAILED attempt=$attempt $site $mode $guard rc=$rc"
    attempt=$((attempt + 1))
    sleep 45
  done
  if [ "$ok" -ne 1 ]; then log "CELL_ABORT $site $mode $guard"; break; fi
done
log "QUEUE_END pid=$$"
