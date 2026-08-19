#!/usr/bin/env python3
"""Consolidate immutable main, transport-recovery, and fuzzy-recovery reports.

The script never executes an episode.  It verifies every source against the
frozen master/site configs, merges by task ID, refuses duplicates or gaps, and
writes evaluator-shaped 30-row reports for the final 2x2 analyser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SITES = ("gitlab", "reddit", "shopping")
CELLS = (
    ("reactive", "off"),
    ("reactive", "on"),
    ("world-model", "off"),
    ("world-model", "on"),
)


def canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen(path: Path, label: str) -> tuple[dict[str, Any], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    unfrozen = dict(payload)
    declared = str(unfrozen.pop("freeze_sha256", ""))
    actual = canonical_sha(unfrozen)
    if not declared or declared != actual:
        raise ValueError(f"{label} freeze mismatch: {declared!r} != {actual!r}")
    return payload, declared


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = sum(int(row["attempted_actions"]) for row in rows)
    executions = sum(int(row["action_execution_successes"]) for row in rows)
    return {
        "episodes": len(rows),
        "successes": sum(bool(row["success"]) for row in rows),
        "success_rate": sum(bool(row["success"]) for row in rows) / len(rows),
        "action_execution_rate": executions / attempts if attempts else 0.0,
        "average_steps": statistics.fmean(float(row["steps"]) for row in rows),
        "average_latency_seconds": statistics.fmean(
            float(row["elapsed_seconds"]) for row in rows
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs" / "webarena_p0_round2_holdout_frozen.json",
    )
    parser.add_argument("--report-dir", type=Path, default=ROOT / "data" / "reports")
    parser.add_argument("--output-prefix", default="webarena_p0_round2_consolidated")
    return parser.parse_args()


def verify_health(
    report: dict[str, Any], *, mode: str, guard: str, release: str, label: str
) -> None:
    if mode != "world-model":
        return
    health = report.get("remote_agent_health")
    if not isinstance(health, dict):
        raise ValueError(f"missing W4 health attestation: {label}")
    if health.get("status") != "ok":
        raise ValueError(f"unhealthy W4 source: {label}")
    if health.get("navigation_guard") != guard:
        raise ValueError(f"W4 guard mismatch: {label}")
    if bool(health.get("semantic_goal_priority")):
        raise ValueError(f"semantic override enabled: {label}")
    if health.get("release_fingerprint_sha256") != release:
        raise ValueError(f"W4 release mismatch: {label}")


def validate_row(
    row: dict[str, Any], *, task_ids: set[int], site: str, mode: str
) -> tuple[int, int]:
    task_id = int(row["task_id"])
    seed = int(row["seed"])
    if task_id not in task_ids or seed != 0:
        raise ValueError(f"unexpected episode identity: {site}/{mode}/{task_id}/{seed}")
    if row.get("site") != site or row.get("mode") != mode:
        raise ValueError(f"episode label mismatch: {site}/{mode}/{task_id}")
    if bool(row.get("uses_expected_answer")) or int(row["steps"]) > 12:
        raise ValueError(f"answer injection or budget violation: {site}/{mode}/{task_id}")
    trajectory = Path(str(row["trajectory_path"]))
    if not trajectory.is_file() or trajectory.stat().st_size <= 0:
        raise ValueError(f"missing trajectory: {trajectory}")
    return task_id, seed


def main() -> int:
    args = parse_args()
    manifest, master_freeze = load_frozen(args.manifest, "master")
    release = str(manifest["release"]["sha256"])
    outputs: list[dict[str, Any]] = []
    for site in SITES:
        site_config_path = (
            ROOT / "configs" / f"webarena_p0_round2_holdout_{site}_frozen.json"
        )
        site_config, site_freeze = load_frozen(site_config_path, f"{site} config")
        if site_config["parent_manifest"]["freeze_sha256"] != master_freeze:
            raise ValueError(f"{site} config parent mismatch")
        expected_order = [int(value) for value in site_config["task_ids"]]
        expected_ids = set(expected_order)
        for mode, guard in CELLS:
            stem = f"{site}_{mode}_guard_{guard}"
            main_path = args.report_dir / f"webarena_p0_round2_holdout_{stem}.json"
            if not main_path.is_file():
                raise ValueError(f"missing main report: {main_path}")
            main_report = json.loads(main_path.read_text(encoding="utf-8"))
            if main_report.get("freeze_sha256") != site_freeze:
                raise ValueError(f"main site freeze mismatch: {main_path}")
            if main_report.get("navigation_guard") != guard:
                raise ValueError(f"main guard mismatch: {main_path}")
            verify_health(
                main_report, mode=mode, guard=guard, release=release, label=str(main_path)
            )

            source_reports: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]] = [
                (main_path, main_report, list(main_report.get("results", {}).get(mode, [])))
            ]
            transport_path = args.report_dir / (
                f"webarena_p0_round2_holdout_{stem}_transport_recovery.json"
            )
            if transport_path.is_file():
                transport_config_path = ROOT / "configs" / (
                    f"webarena_p0_round2_holdout_{stem}_transport_recovery.json"
                )
                transport_config, transport_freeze = load_frozen(
                    transport_config_path, f"{stem} transport config"
                )
                parent = transport_config.get("parent_holdout_report", {})
                if parent.get("site_config_freeze_sha256") != site_freeze:
                    raise ValueError(f"transport parent mismatch: {transport_config_path}")
                transport_report = json.loads(
                    transport_path.read_text(encoding="utf-8")
                )
                if transport_report.get("freeze_sha256") != transport_freeze:
                    raise ValueError(f"transport freeze mismatch: {transport_path}")
                if transport_report.get("navigation_guard") != guard:
                    raise ValueError(f"transport guard mismatch: {transport_path}")
                verify_health(
                    transport_report,
                    mode=mode,
                    guard=guard,
                    release=release,
                    label=str(transport_path),
                )
                source_reports.append(
                    (
                        transport_path,
                        transport_report,
                        list(transport_report.get("results", {}).get(mode, [])),
                    )
                )

            fuzzy_path = args.report_dir / (
                f"webarena_p0_round2_recovery_{stem}.json"
            )
            if fuzzy_path.is_file():
                fuzzy_report = json.loads(fuzzy_path.read_text(encoding="utf-8"))
                if fuzzy_report.get("master_freeze_sha256") != master_freeze:
                    raise ValueError(f"fuzzy master freeze mismatch: {fuzzy_path}")
                if fuzzy_report.get("site_config_freeze_sha256") != site_freeze:
                    raise ValueError(f"fuzzy site freeze mismatch: {fuzzy_path}")
                adapter = fuzzy_report.get("validation_adapter", {})
                if (
                    bool(adapter.get("reference_answers_read"))
                    or bool(adapter.get("local_answer_judge_used"))
                    or bool(fuzzy_report.get("uses_expected_answer"))
                ):
                    raise ValueError(f"invalid fuzzy answer policy: {fuzzy_path}")
                verify_health(
                    fuzzy_report,
                    mode=mode,
                    guard=guard,
                    release=release,
                    label=str(fuzzy_path),
                )
                source_reports.append(
                    (fuzzy_path, fuzzy_report, list(fuzzy_report.get("results", [])))
                )

            rows_by_id: dict[int, dict[str, Any]] = {}
            all_failures: list[dict[str, Any]] = []
            source_audit: list[dict[str, Any]] = []
            for source_path, source_report, rows in source_reports:
                for row in rows:
                    task_id, _ = validate_row(
                        row, task_ids=expected_ids, site=site, mode=mode
                    )
                    if task_id in rows_by_id:
                        raise ValueError(f"duplicate recovered task {task_id}: {source_path}")
                    normalized = dict(row)
                    trajectory = Path(str(row["trajectory_path"]))
                    normalized["trajectory_sha256"] = file_sha(trajectory)
                    normalized["source_report"] = source_path.relative_to(ROOT).as_posix()
                    rows_by_id[task_id] = normalized
                all_failures.extend(source_report.get("failures", []))
                source_audit.append(
                    {
                        "path": source_path.relative_to(ROOT).as_posix(),
                        "sha256": file_sha(source_path),
                        "rows": len(rows),
                        "failures": len(source_report.get("failures", [])),
                    }
                )

            unresolved = [
                failure
                for failure in all_failures
                if int(failure["task_id"]) not in rows_by_id
            ]
            missing = [task_id for task_id in expected_order if task_id not in rows_by_id]
            if unresolved or missing or len(rows_by_id) != 30:
                raise ValueError(
                    f"incomplete {stem}: missing={missing}, unresolved={unresolved}"
                )
            rows = [rows_by_id[task_id] for task_id in expected_order]
            metrics = summarize(rows)
            consolidated = dict(main_report)
            consolidated.update(
                {
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "freeze_sha256": site_freeze,
                    "results": {mode: rows},
                    "failures": [],
                    "agent_metrics": metrics if mode == "reactive" else None,
                    "world_model_agent_metrics": metrics if mode == "world-model" else None,
                    "per_site_metrics": {mode: {site: metrics}},
                    "consolidation": {
                        "master_freeze_sha256": master_freeze,
                        "site_config_freeze_sha256": site_freeze,
                        "release_fingerprint_sha256": release,
                        "source_reports": source_audit,
                        "merge_rule": "Immutable source reports merged by frozen task ID; no episode rerun or outcome replacement.",
                    },
                }
            )
            output = args.report_dir / f"{args.output_prefix}_{stem}.json"
            output.write_text(
                json.dumps(consolidated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            outputs.append(
                {
                    "path": output.relative_to(ROOT).as_posix(),
                    "sha256": file_sha(output),
                    "episodes": len(rows),
                    "successes": metrics["successes"],
                }
            )
    print(json.dumps({"reports": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
