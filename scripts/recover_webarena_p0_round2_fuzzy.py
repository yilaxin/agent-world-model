#!/usr/bin/env python3
"""Recover only frozen holdout episodes blocked by no-answer fuzzy startup.

The adapter returns a non-terminal zero only before any answer exists.  Once
an agent submits an answer, BrowserGym's original official evaluator is used.
It does not read reference answers or replace the answer judge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir("/tmp")

from agent_world_model import ReactiveAgent  # noqa: E402
from agent_world_model.remote_agent import RemotePhase3Agent  # noqa: E402
from browsergym.webarena.task import GenericWebArenaTask  # noqa: E402
from scripts.evaluate_webarena_online import _run_one  # noqa: E402


def canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=("gitlab", "reddit", "shopping"), required=True)
    parser.add_argument("--mode", choices=("reactive", "world-model"), required=True)
    parser.add_argument("--navigation-guard", choices=("on", "off"), required=True)
    parser.add_argument("--remote-agent-url", default=None)
    parser.add_argument("--task-ids", type=int, nargs="*")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs" / "webarena_p0_round2_holdout_frozen.json",
    )
    parser.add_argument("--report-dir", type=Path, default=ROOT / "data" / "reports")
    parser.add_argument(
        "--failure-report",
        type=Path,
        help="Override the report whose OPENAI_API_KEY failures authorize recovery.",
    )
    parser.add_argument(
        "--failure-config",
        type=Path,
        help="Frozen config used by --failure-report; defaults to the site config.",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        help="Override the recovery report path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "trajectories_webarena_p0_round2_recovery",
    )
    return parser.parse_args()


def verify_frozen(payload: dict[str, Any], label: str) -> str:
    unfrozen = dict(payload)
    declared = str(unfrozen.pop("freeze_sha256", ""))
    actual = canonical_sha(unfrozen)
    if not declared or declared != actual:
        raise ValueError(f"{label} freeze mismatch: {declared!r} != {actual!r}")
    return declared


def main() -> int:
    args = parse_args()
    master = json.loads(args.manifest.read_text(encoding="utf-8"))
    master_freeze = verify_frozen(master, "master")
    site_config_path = ROOT / "configs" / f"webarena_p0_round2_holdout_{args.site}_frozen.json"
    site_config = json.loads(site_config_path.read_text(encoding="utf-8"))
    site_freeze = verify_frozen(site_config, "site config")
    if site_config["parent_manifest"]["freeze_sha256"] != master_freeze:
        raise ValueError("site config does not derive from the round-2 master")

    main_report_path = args.failure_report or args.report_dir / (
        f"webarena_p0_round2_holdout_{args.site}_{args.mode}_guard_"
        f"{args.navigation_guard}.json"
    )
    if not main_report_path.is_absolute():
        main_report_path = ROOT / main_report_path
    failure_config_path = args.failure_config or site_config_path
    if not failure_config_path.is_absolute():
        failure_config_path = ROOT / failure_config_path
    failure_config = json.loads(failure_config_path.read_text(encoding="utf-8"))
    failure_config_freeze = verify_frozen(failure_config, "failure config")
    if failure_config_path != site_config_path:
        parent = failure_config.get("parent_holdout_report", {})
        if parent.get("site_config_freeze_sha256") != site_freeze:
            raise ValueError("failure config does not derive from the frozen site config")
    main_report = json.loads(main_report_path.read_text(encoding="utf-8"))
    if main_report.get("freeze_sha256") != failure_config_freeze:
        raise ValueError("failure report config freeze mismatch")
    if main_report.get("navigation_guard") != args.navigation_guard:
        raise ValueError("main report guard mismatch")
    report_mode = "world-model" if main_report.get("world_model_agent_metrics") else "reactive"
    if report_mode != args.mode:
        raise ValueError("main report mode mismatch")

    eligible: dict[int, str] = {}
    for failure in main_report.get("failures", []):
        detail = str(failure.get("error", ""))
        if "OPENAI_API_KEY" in detail:
            eligible[int(failure["task_id"])] = detail
    task_ids = list(args.task_ids or sorted(eligible))
    if not task_ids:
        raise ValueError("no no-answer fuzzy initialization failures to recover")
    if not set(task_ids).issubset(eligible):
        raise ValueError("recovery is restricted to recorded OPENAI_API_KEY failures")
    if not set(task_ids).issubset(set(failure_config["task_ids"])):
        raise ValueError("recovery task is outside the failure config")
    if not set(task_ids).issubset(set(site_config["task_ids"])):
        raise ValueError("recovery task is outside the frozen site config")

    original_validate = GenericWebArenaTask.validate

    def validate_no_answer_as_zero(
        task: GenericWebArenaTask, page: Any, chat_messages: list[dict[str, Any]]
    ) -> tuple[float, bool, str, dict[str, Any]]:
        if not chat_messages or chat_messages[-1].get("role") not in {
            "assistant",
            "infeasible",
        }:
            return 0.0, False, "", {"round2_holdout_no_answer_short_circuit": True}
        return original_validate(task, page, chat_messages)

    GenericWebArenaTask.validate = validate_no_answer_as_zero
    guard_bool = args.navigation_guard == "on"
    remote_health = None
    agent: Any = ReactiveAgent(navigation_guard=guard_bool)
    if args.mode == "world-model":
        remote_url = args.remote_agent_url or (
            "http://127.0.0.1:18761" if guard_bool else "http://127.0.0.1:18760"
        )
        agent = RemotePhase3Agent(
            remote_url,
            bearer_token=os.environ.get("AGENT_WORLD_MODEL_AUTH_TOKEN") or None,
        )
        remote_health = agent.health()
        if remote_health.get("status") != "ok":
            raise ValueError(f"unhealthy remote agent: {remote_health}")
        if remote_health.get("navigation_guard") != args.navigation_guard:
            raise ValueError("remote guard mismatch")
        if bool(remote_health.get("semantic_goal_priority")):
            raise ValueError("semantic_goal_priority must remain disabled")
        if remote_health.get("release_fingerprint_sha256") != master["release"]["sha256"]:
            raise ValueError("remote release fingerprint mismatch")

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    trajectory_dir = (
        args.output_dir
        / args.site
        / f"{args.mode}_guard_{args.navigation_guard}"
        / args.mode
    )
    for task_id in task_ids:
        try:
            row = _run_one(
                f"browsergym/webarena.{task_id}",
                0,
                12,
                trajectory_dir,
                None,
                agent,
                max_attempts=2,
            )
            row.update(
                {
                    "mode": args.mode,
                    "task_id": task_id,
                    "site": args.site,
                    "uses_expected_answer": False,
                    "recovery_validation_adapter": "no_answer_is_nonterminal_zero",
                }
            )
            rows.append(row)
            print(f"task={task_id} success={row['success']} steps={row['steps']}")
        except Exception as error:
            failures.append(
                {"mode": args.mode, "task_id": task_id, "seed": 0, "error": repr(error)}
            )

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "recover frozen holdout episodes blocked by no-answer fuzzy initialization",
        "site": args.site,
        "mode": args.mode,
        "navigation_guard": args.navigation_guard,
        "task_ids": task_ids,
        "seed": 0,
        "step_budget": 12,
        "master_freeze_sha256": master_freeze,
        "site_config_freeze_sha256": site_freeze,
        "failure_config_freeze_sha256": failure_config_freeze,
        "failure_report_path": main_report_path.resolve().relative_to(ROOT).as_posix(),
        "release_fingerprint_sha256": master["release"]["sha256"],
        "remote_agent_health": remote_health,
        "uses_expected_answer": False,
        "validation_adapter": {
            "rule": "Only no-answer validation returns score=0, done=false; submitted answers delegate to the original official evaluator.",
            "reference_answers_read": False,
            "local_answer_judge_used": False,
        },
        "results": rows,
        "failures": failures,
    }
    report_path = args.output_report or args.report_dir / (
        f"webarena_p0_round2_recovery_{args.site}_{args.mode}_guard_"
        f"{args.navigation_guard}.json"
    )
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"report": str(report_path), "rows": len(rows), "failures": len(failures)}, indent=2))
    return 0 if not failures and len(rows) == len(task_ids) else 2


if __name__ == "__main__":
    raise SystemExit(main())
