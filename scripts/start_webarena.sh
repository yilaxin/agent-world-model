#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

source .venv/bin/activate
source .env.webarena

if [[ "$(docker inspect -f '{{.State.Running}}' webarena_verified_reddit 2>/dev/null || true)" != "true" ]]; then
    webarena-verified env start \
        --site reddit \
        --port 9999 \
        --env-ctrl-port 9998 \
        --timeout 300
fi

docker update --restart unless-stopped webarena_verified_reddit >/dev/null
webarena-verified env status --url http://127.0.0.1:9998 --timeout 30

echo "WebArena Reddit: http://127.0.0.1:9999"
echo "WebArena env-ctrl: http://127.0.0.1:9998"
