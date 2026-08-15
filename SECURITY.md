# Security policy

## Supported scope

Security review covers the Python agent, evaluation scripts, inference server,
model/checkpoint loading, trajectory processing, and experiment configuration.
Generated reports, PDFs, frozen evidence, model weights, and benchmark data are
artifacts rather than executable trust anchors.

## Required invariants

- Untrusted benchmark text and page state are data, never executable code.
- Browser actions must pass syntax and visible-element validation before use.
- Model checkpoints must be loaded with `weights_only=True`.
- Remote inference must use a loopback/private tunnel or HTTPS. Public plain
  HTTP endpoints are rejected.
- Set `AGENT_WORLD_MODEL_AUTH_TOKEN` on both evaluator and inference server
  whenever the inference port is reachable by another user or host.
- Do not place passwords, API keys, cookies, bearer tokens, or SSH credentials
  in configs, reports, trajectories, command history, or Git.
- Keep the inference server bound to `127.0.0.1` unless a separately protected
  network boundary and authentication are in place.
- Frozen holdout manifests and release fingerprints are immutable evidence;
  repaired policies require a new release fingerprint and a new holdout.

## Reporting

Report security issues privately to the repository owner. Include the affected
file, entry point, attacker-controlled input, impact, and a minimal reproduction
that does not expose real credentials or user data.
