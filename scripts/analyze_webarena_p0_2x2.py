#!/usr/bin/env python3
"""Validate and analyse the frozen WebArena P0 2x2 holdout.

This script is deliberately outside the frozen agent release. It only reads
completed episode reports and archived trajectories; it cannot change the
policy, navigation guard, model weights, task set, or step budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CELL_SPECS = {
    "reactive_guard_off": ("reactive", "off"),
    "reactive_guard_on": ("reactive", "on"),
    "w4_guard_off": ("world-model", "off"),
    "w4_guard_on": ("world-model", "on"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "configs" / "webarena_p0_holdout_frozen.json",
    )
    parser.add_argument(
        "--report-dir", type=Path, default=PROJECT_ROOT / "data" / "reports"
    )
    parser.add_argument(
        "--trajectory-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories_webarena_p0",
    )
    parser.add_argument(
        "--recovery-report-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "webarena_p0_2x2_analysis.json",
    )
    parser.add_argument(
        "--report-prefix",
        default="webarena_p0",
        help="Filename prefix before _{site}_{mode}_guard_{guard}.json.",
    )
    parser.add_argument(
        "--recovery-prefix",
        default="webarena_p0_recovery",
        help="Filename prefix for evaluator-initialization recovery reports.",
    )
    parser.add_argument(
        "--site-config-template",
        default="configs/webarena_p0_holdout_{site}_frozen.json",
        help="Used to derive per-site freeze hashes when the master omits them.",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20_260_813)
    parser.add_argument(
        "--allow-evaluator-failures",
        action="store_true",
        help="Analyse only the intersection of successfully judged tasks and report exclusions.",
    )
    parser.add_argument(
        "--deterministic-empty-answer-failures",
        action="store_true",
        help="Count missing-key fuzzy-match episodes as failures only when their trajectory contains no submitted answer.",
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quantiles(values: list[float]) -> list[float]:
    values.sort()
    size = len(values)
    return [
        values[int(0.025 * size)],
        values[min(size - 1, int(0.975 * size))],
    ]


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def _cell_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = sum(bool(row["success"]) for row in rows)
    attempts = sum(int(row["attempted_actions"]) for row in rows)
    executions = sum(int(row["action_execution_successes"]) for row in rows)
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_rate": successes / len(rows),
        "success_rate_95ci_wilson": _wilson(successes, len(rows)),
        "action_execution_rate": executions / attempts if attempts else 0.0,
        "average_steps": statistics.fmean(float(row["steps"]) for row in rows),
        "average_latency_seconds": statistics.fmean(
            float(row["elapsed_seconds"]) for row in rows
        ),
        "episode_attempts": sum(int(row["episode_attempts"]) for row in rows),
    }


def _paired_comparison(
    baseline: Mapping[str, float],
    candidate: Mapping[str, float],
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    keys = sorted(baseline)
    if keys != sorted(candidate):
        raise ValueError("paired cell keys do not match")
    baseline_values = [float(baseline[key]) for key in keys]
    candidate_values = [float(candidate[key]) for key in keys]
    differences = [right - left for left, right in zip(baseline_values, candidate_values)]
    baseline_rate = statistics.fmean(baseline_values)
    candidate_rate = statistics.fmean(candidate_values)
    rng = random.Random(seed)
    boot = [
        statistics.fmean(rng.choice(differences) for _ in differences)
        for _ in range(samples)
    ]
    relative = (
        (candidate_rate - baseline_rate) / baseline_rate
        if baseline_rate > 0.0
        else None
    )
    return {
        "paired_task_count": len(keys),
        "baseline_success_rate": baseline_rate,
        "candidate_success_rate": candidate_rate,
        "absolute_improvement_points": 100.0 * (candidate_rate - baseline_rate),
        "absolute_improvement_95ci_points": [100.0 * value for value in _quantiles(boot)],
        "relative_improvement": relative,
        "baseline_only_success": sum(left > right for left, right in zip(baseline_values, candidate_values)),
        "candidate_only_success": sum(right > left for left, right in zip(baseline_values, candidate_values)),
    }


def _cluster_bootstrap_effect(
    per_task: Mapping[str, float], *, samples: int, seed: int
) -> dict[str, Any]:
    values = [float(per_task[key]) for key in sorted(per_task)]
    rng = random.Random(seed)
    boot = [
        statistics.fmean(rng.choice(values) for _ in values)
        for _ in range(samples)
    ]
    return {
        "paired_task_count": len(values),
        "effect_points": 100.0 * statistics.fmean(values),
        "effect_95ci_points": [100.0 * value for value in _quantiles(boot)],
    }


def _trajectory_path(
    row: Mapping[str, Any], trajectory_root: Path, site: str, cell: str, mode: str
) -> Path:
    declared = Path(str(row["trajectory_path"]))
    if declared.is_file():
        return declared
    basename = declared.name
    guard = CELL_SPECS[cell][1]
    candidate = trajectory_root / site / f"{mode}_guard_{guard}" / mode / basename
    if candidate.is_file():
        return candidate
    raise ValueError(f"trajectory is unavailable: {declared}")


def _failure_trajectory_candidates(
    trajectory_root: Path, site: str, mode: str, guard: str, task_id: int, seed: int
) -> list[Path]:
    folder = trajectory_root / site / f"{mode}_guard_{guard}" / mode
    return sorted(folder.glob(f"*webarena.{task_id}_seed{seed}_*.jsonl"))


def _trajectory_has_submitted_answer(path: Path) -> bool:
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        action = str(row.get("action", "")).strip().lower()
        decision_action = str(row.get("decision", {}).get("action", "")).strip().lower()
        if action.startswith("send_msg(") or decision_action.startswith("send_msg("):
            return True
    return False


def main() -> int:
    args = parse_args()
    manifest_path = _resolve(args.manifest)
    report_dir = _resolve(args.report_dir)
    trajectory_root = _resolve(args.trajectory_root)
    recovery_report_dir = _resolve(args.recovery_report_dir)
    output_path = _resolve(args.output)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    unfrozen_manifest = dict(manifest)
    declared_manifest_freeze = str(unfrozen_manifest.pop("freeze_sha256", ""))
    computed_manifest_freeze = hashlib.sha256(
        json.dumps(
            unfrozen_manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if not declared_manifest_freeze or declared_manifest_freeze != computed_manifest_freeze:
        raise ValueError("master manifest freeze hash mismatch")
    expected_release = str(manifest["release"]["sha256"])
    expected_freeze = str(manifest["freeze_sha256"])
    expected_seed = int(manifest.get("seeds", [0])[0])
    step_budget = int(manifest["step_budget_per_episode"])
    site_freezes = dict(manifest.get("site_config_freeze_sha256", {}))
    for site in manifest["sites"]:
        if site in site_freezes:
            continue
        site_config_path = _resolve(Path(args.site_config_template.format(site=site)))
        site_config = json.loads(site_config_path.read_text(encoding="utf-8"))
        unfrozen_site = dict(site_config)
        declared_site_freeze = str(unfrozen_site.pop("freeze_sha256", ""))
        computed_site_freeze = hashlib.sha256(
            json.dumps(
                unfrozen_site,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if not declared_site_freeze or declared_site_freeze != computed_site_freeze:
            raise ValueError(f"site config freeze hash mismatch: {site_config_path}")
        site_freezes[site] = declared_site_freeze

    rows_by_cell: dict[str, list[dict[str, Any]]] = {cell: [] for cell in CELL_SPECS}
    sources: list[dict[str, Any]] = []
    evaluator_failures: list[dict[str, Any]] = []
    deterministic_failure_adjudications: list[dict[str, Any]] = []
    for site in manifest["sites"]:
        expected_ids = {int(value) for value in manifest["selected_task_ids_by_site"][site]}
        for cell, (mode, guard) in CELL_SPECS.items():
            report_path = report_dir / (
                f"{args.report_prefix}_{site}_{mode}_guard_{guard}.json"
            )
            if not report_path.is_file():
                raise ValueError(f"missing report: {report_path}")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report_failures = list(report.get("failures", []))
            if (
                report_failures
                and not args.allow_evaluator_failures
                and not args.deterministic_empty_answer_failures
            ):
                raise ValueError(f"report contains evaluator/infrastructure failures: {report_path}")
            evaluator_failures.extend(
                {"site": site, "cell": cell, **failure} for failure in report_failures
            )
            if str(report.get("navigation_guard")) != guard:
                raise ValueError(f"guard label mismatch: {report_path}")
            expected_site_freeze = str(site_freezes[site])
            if str(report.get("freeze_sha256")) != expected_site_freeze:
                raise ValueError(f"freeze hash mismatch: {report_path}")
            health = report.get("remote_agent_health")
            if mode == "world-model":
                if not isinstance(health, dict):
                    raise ValueError(f"missing remote health attestation: {report_path}")
                if str(health.get("release_fingerprint_sha256")) != expected_release:
                    raise ValueError(f"release fingerprint mismatch: {report_path}")
                if str(health.get("navigation_guard")) != guard:
                    raise ValueError(f"remote guard mismatch: {report_path}")
                if bool(health.get("semantic_goal_priority")):
                    raise ValueError(f"semantic override was enabled: {report_path}")
            rows = list(report.get("results", {}).get(mode, []))
            ids = {int(row["task_id"]) for row in rows}
            if not ids.issubset(expected_ids):
                raise ValueError(f"unexpected task set: {report_path}")
            failed_ids = {int(item["task_id"]) for item in report_failures}
            if ids & failed_ids or ids | failed_ids != expected_ids:
                raise ValueError(f"incomplete or unexpected task set: {report_path}")
            if args.deterministic_empty_answer_failures:
                retained_failures: list[dict[str, Any]] = []
                for failure in report_failures:
                    task_id = int(failure["task_id"])
                    seed = int(failure["seed"])
                    is_missing_key = "OPENAI_API_KEY environment variable must be set" in str(failure["error"])
                    recovery_path = recovery_report_dir / (
                        f"{args.recovery_prefix}_{site}_{mode}_guard_{guard}.json"
                    )
                    if is_missing_key and recovery_path.is_file():
                        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
                        recovery_rows = [
                            row for row in recovery.get("results", [])
                            if int(row["task_id"]) == task_id and int(row["seed"]) == seed
                        ]
                        if len(recovery_rows) != 1 or recovery.get("failures"):
                            raise ValueError(f"invalid recovery report: {recovery_path}")
                        recovery_master_freeze = recovery.get(
                            "freeze_sha256", recovery.get("master_freeze_sha256")
                        )
                        if str(recovery_master_freeze) != expected_freeze:
                            raise ValueError(f"recovery freeze mismatch: {recovery_path}")
                        if str(recovery.get("site_config_freeze_sha256")) != expected_site_freeze:
                            raise ValueError(f"recovery site freeze mismatch: {recovery_path}")
                        if str(recovery.get("release_fingerprint_sha256")) != expected_release:
                            raise ValueError(f"recovery release mismatch: {recovery_path}")
                        adapter = recovery.get("validation_adapter", {})
                        if (
                            bool(adapter.get("reference_answers_read"))
                            or bool(adapter.get("local_answer_judge_used"))
                            or bool(recovery.get("uses_expected_answer"))
                        ):
                            raise ValueError(f"invalid recovery answer policy: {recovery_path}")
                        recovery_health = recovery.get("remote_agent_health")
                        if mode == "world-model":
                            if not isinstance(recovery_health, dict):
                                raise ValueError(f"missing recovery health: {recovery_path}")
                            if str(recovery_health.get("release_fingerprint_sha256")) != expected_release:
                                raise ValueError(f"recovery health release mismatch: {recovery_path}")
                            if str(recovery_health.get("navigation_guard")) != guard:
                                raise ValueError(f"recovery health guard mismatch: {recovery_path}")
                            if bool(recovery_health.get("semantic_goal_priority")):
                                raise ValueError(f"recovery semantic override enabled: {recovery_path}")
                        recovered = dict(recovery_rows[0])
                        trajectory = Path(str(recovered["trajectory_path"]))
                        if not trajectory.is_file() or trajectory.stat().st_size <= 0:
                            raise ValueError(f"missing recovery trajectory: {trajectory}")
                        if _trajectory_has_submitted_answer(trajectory):
                            raise ValueError(f"recovery submitted an answer: {trajectory}")
                        if bool(recovered["success"]):
                            raise ValueError(f"no-answer recovery cannot be successful: {recovery_path}")
                        recovered.update({
                            "trajectory_sha256": _sha256(trajectory),
                            "deterministic_empty_answer_failure": True,
                            "original_evaluator_failure": str(failure["error"]),
                            "recovery_report_path": str(recovery_path),
                            "recovery_report_sha256": _sha256(recovery_path),
                        })
                        rows.append(recovered)
                        deterministic_failure_adjudications.append({
                            "site": site,
                            "cell": cell,
                            "mode": mode,
                            "navigation_guard": guard,
                            "task_id": task_id,
                            "seed": seed,
                            "success": False,
                            "trajectory_path": str(trajectory),
                            "trajectory_sha256": _sha256(trajectory),
                            "recovery_report_path": str(recovery_path),
                            "recovery_report_sha256": _sha256(recovery_path),
                            "rule": "no-answer fuzzy validation is non-terminal zero; submitted answers delegate to the official evaluator; recovered trajectory submitted no answer",
                        })
                    else:
                        retained_failures.append(failure)
                report_failures = retained_failures
                evaluator_failures = [
                    item for item in evaluator_failures
                    if not (item["site"] == site and item["cell"] == cell)
                ]
                evaluator_failures.extend(
                    {"site": site, "cell": cell, **failure}
                    for failure in report_failures
                )
            seen: set[tuple[int, int]] = set()
            for row in rows:
                key = (int(row["task_id"]), int(row["seed"]))
                if key in seen:
                    raise ValueError(f"duplicate episode {key}: {report_path}")
                seen.add(key)
                if key[1] != expected_seed or str(row["site"]) != site:
                    raise ValueError(f"episode identity mismatch {key}: {report_path}")
                if str(row["mode"]) != mode or bool(row.get("uses_expected_answer")):
                    raise ValueError(f"mode or answer-injection violation {key}: {report_path}")
                if int(row["steps"]) > step_budget:
                    raise ValueError(f"step-budget violation {key}: {report_path}")
                trajectory = _trajectory_path(row, trajectory_root, site, cell, mode)
                digest = str(row.get("trajectory_sha256", ""))
                actual_digest = _sha256(trajectory)
                if digest and actual_digest != digest:
                    raise ValueError(f"trajectory digest mismatch {key}: {trajectory}")
                normalized = dict(row)
                normalized["trajectory_sha256"] = actual_digest
                normalized["paired_key"] = f"{site}:{key[0]}:{key[1]}"
                rows_by_cell[cell].append(normalized)
            sources.append({
                "site": site,
                "cell": cell,
                "path": str(report_path),
                "sha256": _sha256(report_path),
            })

    expected_total = int(
        manifest.get(
            "total_unique_tasks",
            sum(
                len(values)
                for values in manifest["selected_task_ids_by_site"].values()
            ),
        )
    )
    maps = {
        cell: {row["paired_key"]: float(bool(row["success"])) for row in rows}
        for cell, rows in rows_by_cell.items()
    }
    common_keys = set.intersection(*(set(values) for values in maps.values()))
    if len(common_keys) != expected_total and not args.allow_evaluator_failures:
        raise ValueError("one or more 2x2 cells are incomplete")
    if not common_keys:
        raise ValueError("the 2x2 cells have no commonly judged tasks")
    maps = {
        cell: {key: values[key] for key in sorted(common_keys)}
        for cell, values in maps.items()
    }

    comparisons = {
        "world_model_effect_guard_off": _paired_comparison(
            maps["reactive_guard_off"], maps["w4_guard_off"],
            samples=args.bootstrap_samples, seed=args.bootstrap_seed,
        ),
        "world_model_effect_guard_on": _paired_comparison(
            maps["reactive_guard_on"], maps["w4_guard_on"],
            samples=args.bootstrap_samples, seed=args.bootstrap_seed + 1,
        ),
        "guard_effect_reactive": _paired_comparison(
            maps["reactive_guard_off"], maps["reactive_guard_on"],
            samples=args.bootstrap_samples, seed=args.bootstrap_seed + 2,
        ),
        "guard_effect_world_model": _paired_comparison(
            maps["w4_guard_off"], maps["w4_guard_on"],
            samples=args.bootstrap_samples, seed=args.bootstrap_seed + 3,
        ),
    }
    keys = sorted(common_keys)
    world_model_main = {
        key: 0.5 * (
            maps["w4_guard_off"][key] - maps["reactive_guard_off"][key]
            + maps["w4_guard_on"][key] - maps["reactive_guard_on"][key]
        )
        for key in keys
    }
    guard_main = {
        key: 0.5 * (
            maps["reactive_guard_on"][key] - maps["reactive_guard_off"][key]
            + maps["w4_guard_on"][key] - maps["w4_guard_off"][key]
        )
        for key in keys
    }
    interaction = {
        key: (
            maps["w4_guard_on"][key] - maps["reactive_guard_on"][key]
            - maps["w4_guard_off"][key] + maps["reactive_guard_off"][key]
        )
        for key in keys
    }
    factorial_effects = {
        "world_model_main_effect_average_across_guard_levels": _cluster_bootstrap_effect(
            world_model_main, samples=args.bootstrap_samples, seed=args.bootstrap_seed + 4
        ),
        "guard_main_effect_average_across_agent_modes": _cluster_bootstrap_effect(
            guard_main, samples=args.bootstrap_samples, seed=args.bootstrap_seed + 5
        ),
        "world_model_by_guard_interaction_difference_in_differences": _cluster_bootstrap_effect(
            interaction, samples=args.bootstrap_samples, seed=args.bootstrap_seed + 6
        ),
    }
    primary = comparisons["world_model_effect_guard_on"]
    relative = primary["relative_improvement"]
    complete_holdout = len(common_keys) == expected_total and not evaluator_failures
    threshold_met = complete_holdout and relative is not None and relative >= 0.10
    claim = {
        "target_relative_improvement": 0.10,
        "primary_cell_contrast": "w4_guard_on minus reactive_guard_on",
        "absolute_improvement_points": primary["absolute_improvement_points"],
        "relative_improvement": relative,
        "relative_improvement_evaluable": relative is not None,
        "point_estimate_meets_target": threshold_met,
        "claim_allowed_from_frozen_holdout": threshold_met,
        "complete_frozen_holdout": complete_holdout,
        "frozen_task_count": expected_total,
        "interpretation": (
            "Observed relative SR improvement reaches the +10% target on the frozen unseen holdout; uncertainty must still be reported."
            if threshold_met
            else "The relative SR +10% target is not established on the frozen unseen holdout."
        ),
    }

    per_site: dict[str, dict[str, dict[str, Any]]] = {}
    for site in manifest["sites"]:
        per_site[site] = {
            cell: _cell_summary([row for row in rows if row["site"] == site])
            for cell, rows in rows_by_cell.items()
        }
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": manifest["benchmark"],
        "freeze_sha256": expected_freeze,
        "release_fingerprint_sha256": expected_release,
        "frozen_before_any_holdout_episode": bool(manifest["frozen_before_any_holdout_episode"]),
        "task_feedback_used": bool(manifest["task_feedback_used"]),
        "sites": list(manifest["sites"]),
        "planned_unique_tasks": expected_total,
        "commonly_judged_unique_tasks": len(common_keys),
        "planned_total_episodes": expected_total * len(CELL_SPECS),
        "judged_total_episodes_in_analysis": len(common_keys) * len(CELL_SPECS),
        "step_budget_per_episode": step_budget,
        "cell_metrics": {cell: _cell_summary(rows) for cell, rows in rows_by_cell.items()},
        "per_site_metrics": per_site,
        "paired_comparisons": comparisons,
        "factorial_effects": factorial_effects,
        "relative_sr_plus_10_claim": claim,
        "attribution_rule": "Guard effects are shared-navigation effects. Only paired W4-minus-reactive contrasts estimate world-model contribution.",
        "scope_limit": (
            f"This is a frozen {expected_total}-task, three-site Classic WebArena "
            "holdout, not the full benchmark success rate."
        ),
        "source_reports": sources,
        "evaluator_failures": evaluator_failures,
        "deterministic_failure_adjudications": deterministic_failure_adjudications,
        "episode_evidence": [
            {
                "site": row["site"],
                "cell": cell,
                "mode": row["mode"],
                "task_id": int(row["task_id"]),
                "seed": int(row["seed"]),
                "success": bool(row["success"]),
                "steps": int(row["steps"]),
                "trajectory_path": row["trajectory_path"],
                "trajectory_sha256": row["trajectory_sha256"],
                "deterministic_empty_answer_failure": bool(
                    row.get("deterministic_empty_answer_failure", False)
                ),
            }
            for cell, rows in rows_by_cell.items()
            for row in rows
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        key: value
        for key, value in payload.items()
        if key not in {"per_site_metrics", "source_reports", "episode_evidence"}
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
