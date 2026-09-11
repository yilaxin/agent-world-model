#!/usr/bin/env bash
# Unattended supervisor for the Round-4 WebArena world-model evaluation.
#
# Repairs the pieces the evaluation depends on, so a long run does not need a
# human watching it:
#   * restarts the SSH tunnel from WSL to the GPU host when it disappears
#   * restarts the two frozen inference services when the tunnel is up but the
#     /health endpoints stop answering (or after the GPU instance reboots)
#   * restarts the evaluation queue when it is no longer running and the four
#     world-model cells are still incomplete
#
# It never modifies the frozen release code or the frozen site configs.
set -uo pipefail

repo="${ROUND4_REPO:-/home/filp/agent_world_model}"
key="${ROUND4_SSH_KEY:-/home/filp/.ssh/agent_world_model_gpu_current}"
gpu_host="${ROUND4_GPU_HOST:-connect.westc.seetacloud.com}"
gpu_port="${ROUND4_GPU_PORT:-57845}"
gpu_dir="${ROUND4_GPU_DIR:-/root/autodl-tmp/agent_world_model_round4}"
gpu_python="${ROUND4_GPU_PYTHON:-/root/miniconda3/bin/python}"
expected_fingerprint="7e34a1e3c74252e8c3ab6ff6b29e2e40eda934e58d27a589c2e528d37c117f32"
max_queue_restarts="${ROUND4_MAX_QUEUE_RESTARTS:-5}"
log_file="$repo/tmp/round4_supervisor.log"

cd "$repo" || exit 1
mkdir -p tmp

log() { echo "$(date -u +%FT%TZ) $*" >>"$log_file"; }

health_all() {
  local off on
  off=$(curl -fsS --max-time 6 http://127.0.0.1:18760/health 2>/dev/null) || return 1
  on=$(curl -fsS --max-time 6 http://127.0.0.1:18761/health 2>/dev/null) || return 1
  case "$off" in *"$expected_fingerprint"*) ;; *) return 1 ;; esac
  case "$on" in *"$expected_fingerprint"*) ;; *) return 1 ;; esac
  return 0
}

tunnel_alive() { pgrep -f "L 127.0.0.1:18760:127.0.0.1:18760" >/dev/null 2>&1; }

queue_alive() {
  pgrep -f "run_webarena_p0_round4_cell" >/dev/null 2>&1 && return 0
  pgrep -f "round4_queue.sh" >/dev/null 2>&1 && return 0
  pgrep -f "QUEUE2_START" >/dev/null 2>&1 && return 0
  return 1
}

start_tunnel() {
  log "ACTION restart_tunnel"
  setsid -f bash -c "while true; do ssh -N -i $key -p $gpu_port -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -L 127.0.0.1:18760:127.0.0.1:18760 -L 127.0.0.1:18761:127.0.0.1:18761 root@$gpu_host >>$repo/tmp/round4_gpu_tunnel.log 2>&1; sleep 10; done"
}

restart_servers() {
  local now
  now=$(date +%s)
  if [ $(( now - last_server_restart )) -lt 600 ]; then
    return 0
  fi
  last_server_restart=$now
  log "ACTION restart_inference_services"
  ssh -i "$key" -p "$gpu_port" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=15 root@"$gpu_host" "cd $gpu_dir && bash -s" >>"$log_file" 2>&1 <<REMOTE
pkill -f serve_phase3_inference.py >/dev/null 2>&1 || true
sleep 2
mkdir -p logs
nohup $gpu_python scripts/serve_phase3_inference.py --ensemble-manifest artifacts/phase4/world_model_ensemble_w4.json --alignment-checkpoint artifacts/phase3/structure_aligner_best.pt --planning-config configs/phase3_planner.json --device cuda --host 127.0.0.1 --port 18760 --navigation-guard off --mask-exceptions >logs/round4_inference_off.log 2>&1 </dev/null &
nohup $gpu_python scripts/serve_phase3_inference.py --ensemble-manifest artifacts/phase4/world_model_ensemble_w4.json --alignment-checkpoint artifacts/phase3/structure_aligner_best.pt --planning-config configs/phase3_planner.json --device cuda --host 127.0.0.1 --port 18761 --navigation-guard on --mask-exceptions >logs/round4_inference_on.log 2>&1 </dev/null &
sleep 20
for p in 18760 18761; do printf "port_%s=" "\$p"; curl -fsS --max-time 5 http://127.0.0.1:\$p/health || echo DOWN; echo; done
REMOTE
}

cells_complete() {
  ./.venv/bin/python - <<'PY'
import json
import os

complete = True
for site in ("gitlab", "shopping"):
    for guard in ("off", "on"):
        path = f"data/reports/webarena_p0_round4_holdout_{site}_world-model_guard_{guard}.json"
        if not os.path.exists(path):
            complete = False
            continue
        try:
            report = json.load(open(path, encoding="utf-8"))
        except Exception:
            complete = False
            continue
        rows = (report.get("results") or {}).get("world-model") or []
        if len(rows) != 120 or report.get("failures"):
            complete = False
print("COMPLETE" if complete else "INCOMPLETE")
PY
}

start_queue() {
  rmdir /tmp/round4_queue.lock >/dev/null 2>&1 || true
  log "ACTION restart_queue"
  setsid -f bash "$repo/round4_queue.sh" >>"$repo/tmp/round4_queue.log" 2>&1
}

log "SUPERVISOR_START pid=$$"
queue_restarts=0
complete_logged=0
cap_logged=0
last_server_restart=0

while true; do
  if ! health_all; then
    if ! tunnel_alive; then
      start_tunnel
      sleep 20
    fi
    if ! health_all; then
      if ssh -i "$key" -p "$gpu_port" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=15 root@"$gpu_host" 'echo GPU_SSH_OK' >/dev/null 2>&1; then
        restart_servers
      else
        log "GPU_UNREACHABLE ssh_failed"
        sleep 60
      fi
    fi
  fi

  if ! queue_alive; then
    if [ "$(cells_complete)" = "COMPLETE" ]; then
      if [ "$complete_logged" -eq 0 ]; then log "ALL_CELLS_COMPLETE"; complete_logged=1; fi
    elif [ "$queue_restarts" -lt "$max_queue_restarts" ]; then
      queue_restarts=$((queue_restarts + 1))
      start_queue
      log "QUEUE_RESTART n=$queue_restarts"
    elif [ "$cap_logged" -eq 0 ]; then
      log "QUEUE_RESTART_CAP_REACHED n=$queue_restarts"
      cap_logged=1
    fi
  fi

  sleep 60
done
