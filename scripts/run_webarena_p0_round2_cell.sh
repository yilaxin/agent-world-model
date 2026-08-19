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
  gitlab) site_port=8023; ctrl_port=8022; ready_url=http://localhost:8023/users/sign_in ;;
  reddit) site_port=9999; ctrl_port=9998; ready_url=http://localhost:9999/login ;;
  shopping) site_port=7770; ctrl_port=7771; ready_url=http://localhost:7770/customer/account/login ;;
  *) echo "unsupported site: $site" >&2; exit 64 ;;
esac
[[ "$mode" == "reactive" || "$mode" == "world-model" ]] || exit 64
[[ "$guard" == "on" || "$guard" == "off" ]] || exit 64
if [[ "$guard" == "on" ]]; then remote_port=18761; else remote_port=18760; fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
source .venv/bin/activate
lock_dir="/tmp/webarena_p0_round2_${site}.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "site already has an active round-2 P0 cell: $site" >&2
  exit 75
fi
release_lock() { rmdir "$lock_dir" >/dev/null 2>&1 || true; }
trap release_lock EXIT

export WA_GITLAB=http://localhost:8023
export WA_REDDIT=http://localhost:9999
export WA_SHOPPING=http://localhost:7770
export WA_SHOPPING_ADMIN=http://localhost:7780
export WA_WIKIPEDIA=http://localhost:8888
export WA_MAP=http://localhost:3000
export WA_HOMEPAGE=http://localhost:4399
export PYTHONSAFEPATH=1

config="configs/webarena_p0_round2_holdout_${site}_frozen.json"
report="data/reports/webarena_p0_round2_holdout_${site}_${mode}_guard_${guard}.json"
output_dir="data/trajectories_webarena_p0_round2_holdout/${site}/${mode}_guard_${guard}"

python - "$config" <<'PY'
import hashlib,json,sys
p=json.load(open(sys.argv[1],encoding="utf-8"))
f=dict(p); declared=f.pop("freeze_sha256")
actual=hashlib.sha256(json.dumps(f,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
if declared != actual: raise SystemExit(f"site freeze mismatch: {declared} != {actual}")
if len(p["task_ids"]) != 30 or p["seeds"] != [0]: raise SystemExit("invalid task or seed count")
if p["reactive_step_budget"] != 12 or p["world_model_step_budget"] != 12: raise SystemExit("budget mismatch")
print("ROUND2_SITE_FREEZE_OK",declared)
PY

if [[ -f "$report" ]]; then
  if python - "$report" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding="utf-8"))
mode="world-model" if p.get("world_model_agent_metrics") else "reactive"
rows=p.get("results",{}).get(mode,[])
if p.get("failures") or len(rows)!=30: raise SystemExit(1)
print("CELL_ALREADY_COMPLETE",sys.argv[1])
PY
  then
    release_lock
    trap - EXIT
    exit 0
  fi
  incomplete="${report%.json}.incomplete_$(date -u +%Y%m%dT%H%M%SZ).json"
  mv "$report" "$incomplete"
  echo "ARCHIVED_INCOMPLETE_REPORT $incomplete"
fi

cleanup() { webarena-verified env stop --site "$site" --timeout 60 >/dev/null 2>&1 || true; }
cleanup_and_unlock() { cleanup; release_lock; }
trap cleanup_and_unlock EXIT
cleanup
webarena-verified env start --site "$site" --port "$site_port" --env-ctrl-port "$ctrl_port" --timeout 900

# Verified may return as soon as one HTTP probe succeeds while GitLab is still
# warming.  Require Docker health for GitLab and a fresh page response for all
# sites before creating the first BrowserGym episode.
if [[ "$site" == "gitlab" ]]; then
  for _ in $(seq 1 180); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' webarena_verified_gitlab 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && break
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
            if response.status < 500:
                print("ROUND2_SITE_READY",url,response.status)
                break
    except urllib.error.HTTPError as error:
        if error.code < 500:
            print("ROUND2_SITE_READY",url,error.code)
            break
        if attempt == 59:
            raise
    except Exception as error:
        if attempt == 59: raise
    time.sleep(2)
else:
    raise SystemExit("site did not become ready")
PY

python scripts/evaluate_webarena_online.py \
  --config "$config" \
  --mode "$mode" \
  --navigation-guard "$guard" \
  --remote-agent-url "http://localhost:${remote_port}" \
  --output-dir "$output_dir" \
  --report "$report"
cleanup
release_lock
trap - EXIT
echo "ROUND2_P0_CELL_COMPLETE site=$site mode=$mode guard=$guard"
