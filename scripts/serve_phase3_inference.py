#!/usr/bin/env python3
"""Serve the trained phase-three Agent for a separately deployed browser env."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase3_agent import Phase3WorldModelAgent  # noqa: E402
from agent_world_model.phase3_planning import PlanningConfig  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensemble-manifest", type=Path, required=True)
    parser.add_argument("--alignment-checkpoint", type=Path, required=True)
    parser.add_argument("--planning-config", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.planning_config.read_text(encoding="utf-8"))
    agent = Phase3WorldModelAgent(
        ensemble_manifest=args.ensemble_manifest,
        alignment_checkpoint=args.alignment_checkpoint,
        device=args.device,
        planning_config=PlanningConfig(**config["planning"]),
        max_candidates=int(config["candidate_generation"]["max_candidates"]),
    )

    class Handler(BaseHTTPRequestHandler):
        server_version = "Phase3Inference/1.0"

        def _json(self, status: int, payload: dict[str, object]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(200, {"status": "ok", "device": str(agent.predictor.device)})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/decide":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 2_000_000:
                    raise ValueError("request body must be between 1 byte and 2 MB")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                decision = agent.decide(
                    body["state"],
                    body.get("recent_actions", []),
                    direct_answer=body.get("direct_answer"),
                )
                self._json(200, decision.to_dict())
            except Exception as error:  # keep evaluator failure auditable
                self._json(400, {"error": type(error).__name__, "detail": str(error)})

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.client_address[0]} {format % args}", flush=True)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        json.dumps(
            {"status": "ready", "host": args.host, "port": args.port, "device": str(agent.predictor.device)},
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

