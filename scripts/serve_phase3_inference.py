#!/usr/bin/env python3
"""Serve the trained phase-three Agent for a separately deployed browser env."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import ssl
import sys
import threading
import time
import ipaddress
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase3_agent import Phase3WorldModelAgent  # noqa: E402
from agent_world_model.phase3_planning import PlanningConfig  # noqa: E402
from agent_world_model.rate_limiter import RateLimiter  # noqa: E402
from agent_world_model.release_fingerprint import (  # noqa: E402
    release_files,
    release_fingerprint,
)


def _is_loopback_bind(host: str) -> bool:
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensemble-manifest", type=Path, required=True)
    parser.add_argument("--alignment-checkpoint", type=Path, required=True)
    parser.add_argument("--planning-config", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--auth-token-env",
        default="AGENT_WORLD_MODEL_AUTH_TOKEN",
        help="Environment variable holding the bearer token required beyond loopback.",
    )
    parser.add_argument("--max-concurrent-requests", type=int, default=1)
    parser.add_argument(
        "--semantic-goal-priority",
        action="store_true",
        help="Prefer unrepeated visible controls that strongly match the goal.",
    )
    parser.add_argument(
        "--navigation-guard",
        choices=("on", "off"),
        default="on",
        help="Enable or disable the frozen shared WebArena navigation guard.",
    )
    parser.add_argument(
        "--tls-cert",
        type=Path,
        help="Optional PEM certificate chain for HTTPS. Requires --tls-key.",
    )
    parser.add_argument(
        "--tls-key",
        type=Path,
        help="Optional PEM private key for HTTPS. Requires --tls-cert.",
    )
    parser.add_argument(
        "--allow-client-ips",
        default="",
        help="Comma-separated client IP allowlist. Empty means any client at the bind address.",
    )
    parser.add_argument(
        "--rate-limit-rps",
        type=float,
        default=0.0,
        help="Optional per-client request rate limit in requests/second (0 disables).",
    )
    parser.add_argument(
        "--mask-exceptions",
        action="store_true",
        help="Return generic error details to clients and log the full traceback server-side.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.tls_cert) != bool(args.tls_key):
        raise ValueError("--tls-cert and --tls-key must be provided together")
    if args.tls_cert and not args.tls_cert.exists():
        raise ValueError(f"TLS certificate not found: {args.tls_cert}")
    if args.tls_key and not args.tls_key.exists():
        raise ValueError(f"TLS private key not found: {args.tls_key}")
    allow_ips: set[str] | None = None
    if args.allow_client_ips.strip():
        allow_ips = {
            str(ipaddress.ip_address(part.strip()))
            for part in args.allow_client_ips.split(",")
            if part.strip()
        }
        if not allow_ips:
            raise ValueError("--allow-client-ips contained no valid addresses")
    rate_limiter = RateLimiter(args.rate_limit_rps)

    if args.max_concurrent_requests != 1:
        raise ValueError("this deterministic inference server supports one request at a time")
    auth_token = os.environ.get(args.auth_token_env, "")
    loopback_bind = _is_loopback_bind(args.host)
    if not loopback_bind and not auth_token:
        raise ValueError(
            "AGENT_WORLD_MODEL_AUTH_TOKEN is required when inference binds beyond loopback"
        )
    if not loopback_bind and not args.tls_cert:
        raise ValueError(
            "--tls-cert and --tls-key are required when inference binds beyond loopback"
        )
    config = json.loads(args.planning_config.read_text(encoding="utf-8"))
    agent = Phase3WorldModelAgent(
        ensemble_manifest=args.ensemble_manifest,
        alignment_checkpoint=args.alignment_checkpoint,
        device=args.device,
        planning_config=PlanningConfig(**config["planning"]),
        max_candidates=int(config["candidate_generation"]["max_candidates"]),
        semantic_goal_priority=args.semantic_goal_priority,
        navigation_guard=args.navigation_guard == "on",
    )
    release = release_fingerprint(
        release_files(
            PROJECT_ROOT,
            args.ensemble_manifest,
            args.alignment_checkpoint,
            args.planning_config,
        ),
        root=PROJECT_ROOT,
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

        def _authorized(self) -> bool:
            if not auth_token:
                return True
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {auth_token}"
            return hmac.compare_digest(supplied, expected)

        def _require_authorized(self) -> bool:
            if self._authorized():
                return True
            self._json(401, {"error": "unauthorized"})
            return False

        def _require_allowlisted(self) -> bool:
            client_ip = self.client_address[0]
            if allow_ips is not None and client_ip not in allow_ips:
                self._json(403, {"error": "forbidden"})
                return False
            if not rate_limiter.allow(client_ip):
                self._json(429, {"error": "rate limited"})
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            if not self._require_allowlisted():
                return
            if not self._require_authorized():
                return
            if self.path == "/health":
                self._json(
                    200,
                    {
                        "status": "ok",
                        "device": str(agent.predictor.device),
                        "navigation_guard": args.navigation_guard,
                        "semantic_goal_priority": bool(args.semantic_goal_priority),
                        "release_fingerprint_sha256": release["sha256"],
                        "authentication_required": bool(auth_token),
                    },
                )
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._require_allowlisted():
                return
            if not self._require_authorized():
                return
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
                print(
                    json.dumps(
                        {
                            "client": self.client_address[0],
                            "error_type": type(error).__name__,
                            "detail": str(error),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if args.mask_exceptions:
                    self._json(400, {"error": "bad_request", "detail": "request failed"})
                else:
                    self._json(
                        400,
                        {"error": type(error).__name__, "detail": str(error)},
                    )

        def log_message(self, format: str, *args: object) -> None:
            try:
                print(f"{self.client_address[0]} {format % args}", flush=True)
            except OSError:
                # A detached evaluator service may not retain its launching
                # terminal. Request handling must not depend on stdout.
                pass

    # Keep the service single-threaded so the declared concurrency invariant is real.
    server = HTTPServer((args.host, args.port), Handler)
    if args.tls_cert is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(args.tls_cert), keyfile=str(args.tls_key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        transport = "https"
    else:
        transport = "http"
    print(
        json.dumps(
            {
                "status": "ready",
                "host": args.host,
                "port": args.port,
                "transport": transport,
                "tls_enabled": args.tls_cert is not None,
                "client_ip_allowlist": args.allow_client_ips or None,
                "rate_limit_rps": rate_limiter.rate or None,
                "exception_masking": bool(args.mask_exceptions),
                "device": str(agent.predictor.device),
                "navigation_guard": args.navigation_guard,
                "semantic_goal_priority": bool(args.semantic_goal_priority),
                "release_fingerprint_sha256": release["sha256"],
                "authentication_required": bool(auth_token),
            },
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

