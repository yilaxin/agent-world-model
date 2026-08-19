#!/usr/bin/env python3
"""Evaluate the complete phase-three planner on the held-out trajectory split."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402

from agent_world_model.phase2_metrics import evaluate_thresholds  # noqa: E402
from agent_world_model.phase2_ensemble import EnsembleWorldModelPredictor  # noqa: E402
from agent_world_model.phase2_training import WorldModelPredictor, load_jsonl  # noqa: E402
from agent_world_model.phase3_candidates import (  # noqa: E402
    AXTreeCandidateGenerator,
    candidate_set_entropy,
    validate_action,
)
from agent_world_model.phase3_planning import (  # noqa: E402
    ConfidenceAdaptivePlanner,
    PlanningConfig,
)
from agent_world_model.reactive_agent import ReactiveAgent, parse_elements  # noqa: E402
from agent_world_model.structure_alignment import StructureAlignmentPredictor  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase3_planner.json",
    )
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--ensemble-manifest", type=Path)
    parser.add_argument("--alignment-checkpoint", type=Path)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dataset-dir", type=Path, default=PROJECT_ROOT / "data" / "phase2")
    parser.add_argument("--trajectory-dir", action="append", type=Path, default=[])
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def raw_index(directories: list[Path]) -> dict[tuple[str, int, str], dict[str, Any]]:
    result: dict[tuple[str, int, str], dict[str, Any]] = {}
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.jsonl")):
            for record in load_jsonl(path):
                key = (
                    str(record.get("episode_id") or record.get("run_id") or ""),
                    int(record.get("step_index", 0) or 0),
                    str(record.get("action", "")),
                )
                result[key] = record
    return result


def is_risky(record: Mapping[str, Any]) -> bool:
    risks = record["risks"]
    signals = record["task_signals"]
    return bool(
        risks["stalled"]
        or risks["goal_deviation"]
        or risks["severe_failure"]
        or signals["invalid_action"]
    )


def mean_or_zero(values: list[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    ensemble_manifest = args.ensemble_manifest or (
        project_path(config["outputs"]["ensemble_manifest"])
        if config["outputs"].get("ensemble_manifest")
        else None
    )
    checkpoint = args.checkpoint or project_path(config["outputs"]["checkpoint"])
    output = args.output or project_path(config["outputs"]["evaluation_report"])
    dataset_dir = args.dataset_dir if args.dataset_dir.is_absolute() else PROJECT_ROOT / args.dataset_dir
    records = load_jsonl(dataset_dir / "test.jsonl")
    if args.limit:
        records = records[: args.limit]
    trajectories = raw_index(
        [project_path(path) for path in config["evaluation"]["trajectory_directories"]]
        + [project_path(path) for path in args.trajectory_dir]
    )

    predictor = (
        EnsembleWorldModelPredictor(ensemble_manifest, device=args.device)
        if ensemble_manifest and ensemble_manifest.exists()
        else WorldModelPredictor(checkpoint, device=args.device)
    )
    planner = ConfidenceAdaptivePlanner(
        predictor,
        PlanningConfig(**config["planning"]),
    )
    alignment_checkpoint = args.alignment_checkpoint or (
        project_path(config["outputs"]["alignment_checkpoint"])
        if config["outputs"].get("alignment_checkpoint")
        else None
    )
    alignment = (
        StructureAlignmentPredictor(alignment_checkpoint, device=str(predictor.device))
        if alignment_checkpoint and alignment_checkpoint.exists()
        else None
    )
    generator = AXTreeCandidateGenerator(
        max_candidates=int(config["candidate_generation"]["max_candidates"]),
        alignment_scorer=alignment,
    )
    reactive = ReactiveAgent()

    matched = 0
    candidate_total = 0
    candidate_valid = 0
    source_covered = 0
    safe_source_total = 0
    safe_source_covered = 0
    positive_total = 0
    risky_total = 0
    method_counts: dict[str, Counter[str]] = {
        "reactive": Counter(),
        "w0_one_step": Counter(),
        "w1_structure": Counter(),
        "w2_multiscale": Counter(),
        "phase3": Counter(),
    }
    base_planning_config = PlanningConfig(**config["planning"])
    w1_planner = ConfidenceAdaptivePlanner(
        predictor,
        replace(
            base_planning_config,
            min_horizon=1,
            max_horizon=1,
            long_term_weight=0.0,
            uncertainty_weight=0.0,
        ),
    )
    w2_planner = ConfidenceAdaptivePlanner(
        predictor,
        replace(base_planning_config, uncertainty_weight=0.0),
    )
    horizon_counts: dict[int, Counter[str]] = {1: Counter(), 2: Counter(), 3: Counter()}
    horizon_latencies: dict[int, list[float]] = {1: [], 2: [], 3: []}
    confidence_rows: list[tuple[float, float]] = []
    modes: Counter[str] = Counter()
    horizons: Counter[int] = Counter()
    latencies_ms: list[float] = []
    candidate_counts: list[float] = []
    candidate_entropy: list[float] = []
    confidences: list[float] = []
    chosen_structure: list[float] = []
    explanation_checks = 0
    finite_horizon_checks = 0
    examples: list[dict[str, Any]] = []

    for record in records:
        key = (record["episode_id"], int(record["step_index"]), record["action"])
        raw = trajectories.get(key)
        if raw is None:
            continue
        matched += 1
        state = raw["state"]
        candidates = generator.generate(state)
        actions = [candidate.action for candidate in candidates]
        candidate_counts.append(float(len(candidates)))
        candidate_entropy.append(candidate_set_entropy(candidates))
        candidate_total += len(candidates)
        visible_ids = {element.bid for element in parse_elements(state["axtree"]["text"])}
        candidate_valid += sum(validate_action(action, visible_ids)[0] for action in actions)
        covered = record["action"] in actions
        source_covered += int(covered)
        risky = is_risky(record)
        if not risky:
            safe_source_total += 1
            safe_source_covered += int(covered)

        fallback = reactive.decide(state).action
        if torch.cuda.is_available() and predictor.device.type == "cuda":
            torch.cuda.synchronize(predictor.device)
        started = time.perf_counter()
        decision = planner.plan(
            record["state_vector"],
            candidates,
            fallback_action=fallback,
        )
        if torch.cuda.is_available() and predictor.device.type == "cuda":
            torch.cuda.synchronize(predictor.device)
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        w0_rows = predictor.rank_actions(record["state_vector"], actions)
        w0_action = w0_rows[0]["action"] if w0_rows else fallback
        w1_rows = w1_planner._rollout(
            record["state_vector"], candidates, horizon=1, world_influence=1.0
        )
        w2_rows = w2_planner._rollout(
            record["state_vector"], candidates, horizon=3, world_influence=1.0
        )
        w1_action = w1_rows[0].action if w1_rows else fallback
        w2_action = w2_rows[0].action if w2_rows else fallback

        for fixed_horizon in (1, 2, 3):
            if torch.cuda.is_available() and predictor.device.type == "cuda":
                torch.cuda.synchronize(predictor.device)
            horizon_started = time.perf_counter()
            fixed_rows = planner._rollout(
                record["state_vector"], candidates, horizon=fixed_horizon, world_influence=1.0
            )
            if torch.cuda.is_available() and predictor.device.type == "cuda":
                torch.cuda.synchronize(predictor.device)
            horizon_latencies[fixed_horizon].append((time.perf_counter() - horizon_started) * 1000.0)
            fixed_action = fixed_rows[0].action if fixed_rows else fallback
            horizon_counts[fixed_horizon]["source_agreement"] += int(fixed_action == record["action"])

        selected = {
            "reactive": fallback,
            "w0_one_step": w0_action,
            "w1_structure": w1_action,
            "w2_multiscale": w2_action,
            "phase3": decision.action,
        }
        success = bool(record["risks"]["success"])
        positive_total += int(success)
        risky_total += int(risky)
        for method, action in selected.items():
            method_counts[method]["source_agreement"] += int(action == record["action"])
            if success:
                method_counts[method]["positive_source_agreement"] += int(action == record["action"])
            if risky:
                method_counts[method]["risky_source_diversion"] += int(action != record["action"])

        modes[decision.mode] += 1
        horizons[decision.horizon] += 1
        confidences.append(decision.confidence)
        quality_error = float(
            (success and decision.action != record["action"])
            or (risky and decision.action == record["action"])
        )
        confidence_rows.append((decision.confidence, quality_error))
        finite_horizon_checks += int(0 <= decision.horizon <= 3)
        if decision.ranked_plans:
            best = decision.ranked_plans[0]
            chosen_structure.append(best.structure_score)
            explanation_checks += int(
                bool(best.action_sequence)
                and bool(best.rollout_steps)
                and all(
                    {
                        "progress",
                        "reward",
                        "uncertainty",
                        "state_delta_probabilities",
                        "task_signal_probabilities",
                        "risk_probabilities",
                    }.issubset(step)
                    for step in best.rollout_steps
                )
            )

        if len(examples) < 12:
            examples.append(
                {
                    "example_id": record["example_id"],
                    "task_id": record["task_id"],
                    "instruction": record["instruction"],
                    "recorded_action": record["action"],
                    "recorded_labels": {
                        "success": success,
                        "risky": risky,
                    },
                    "candidate_count": len(candidates),
                    "reactive_action": fallback,
                    "w0_action": w0_action,
                    "phase3_decision": decision.to_dict(),
                }
            )

    denominator = max(1, matched)
    methods: dict[str, Any] = {}
    for method, counts in method_counts.items():
        methods[method] = {
            "recorded_action_agreement": counts["source_agreement"] / denominator,
            "positive_recorded_action_agreement": counts["positive_source_agreement"] / max(1, positive_total),
            "risky_recorded_action_diversion": counts["risky_source_diversion"] / max(1, risky_total),
        }
    planned = modes["planned"] + modes["planned_short"]
    confidence_bands: dict[str, dict[str, float]] = {}
    for name, lower, upper in (
        ("low", 0.0, float(config["planning"]["medium_confidence"])),
        ("medium", float(config["planning"]["medium_confidence"]), float(config["planning"]["high_confidence"])),
        ("high", float(config["planning"]["high_confidence"]), 1.000001),
    ):
        rows = [error for confidence, error in confidence_rows if lower <= confidence < upper]
        confidence_bands[name] = {
            "count": float(len(rows)),
            "coverage": len(rows) / denominator,
            "proxy_risk": mean_or_zero(rows),
        }
    confidence_sorted = sorted(confidence_rows, reverse=True)
    coverage_risk = []
    for coverage in (0.25, 0.50, 0.75, 1.0):
        count = max(1, int(len(confidence_sorted) * coverage + 0.999999))
        coverage_risk.append(
            {
                "coverage": count / denominator,
                "proxy_risk": mean_or_zero([error for _, error in confidence_sorted[:count]]),
                "count": count,
            }
        )
    metrics = {
        "examples_requested": len(records),
        "examples_evaluated": matched,
        "raw_state_match_rate": matched / max(1, len(records)),
        "candidate_schema_valid_rate": candidate_valid / max(1, candidate_total),
        "recorded_action_recall_at_k": source_covered / denominator,
        "safe_recorded_action_recall_at_k": safe_source_covered / max(1, safe_source_total),
        "average_candidate_count": mean_or_zero(candidate_counts),
        "average_candidate_type_entropy": mean_or_zero(candidate_entropy),
        "positive_example_count": positive_total,
        "risky_example_count": risky_total,
        "methods": methods,
        "model_ladder": {
            "B0": "reactive",
            "W0": "w0_one_step",
            "W1": "w1_structure",
            "W2": "w2_multiscale",
            "W3": "phase3",
        },
        "decision_modes": dict(modes),
        "horizon_distribution": {str(key): value for key, value in sorted(horizons.items())},
        "planned_decision_rate": planned / denominator,
        "finite_horizon_compliance": finite_horizon_checks / denominator,
        "explanation_completeness": explanation_checks / denominator,
        "average_confidence": mean_or_zero(confidences),
        "confidence_coverage": confidence_bands,
        "coverage_risk_curve": coverage_risk,
        "horizon_ablation": {
            str(horizon): {
                "recorded_action_agreement": counts["source_agreement"] / denominator,
                "latency_ms_mean": mean_or_zero(horizon_latencies[horizon]),
            }
            for horizon, counts in horizon_counts.items()
        },
        "average_chosen_structure_score": mean_or_zero(chosen_structure),
        "latency_ms": {
            "mean": mean_or_zero(latencies_ms),
            "median": float(statistics.median(latencies_ms)) if latencies_ms else 0.0,
            "p95": (
                float(sorted(latencies_ms)[max(0, int(len(latencies_ms) * 0.95) - 1)])
                if latencies_ms
                else 0.0
            ),
        },
    }
    acceptance = evaluate_thresholds(metrics, config["evaluation"]["acceptance_thresholds"])
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 3,
        "device": str(predictor.device),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": (
            torch.cuda.get_device_name(predictor.device)
            if predictor.device.type == "cuda"
            else None
        ),
        "checkpoint": str(checkpoint),
        "ensemble_manifest": str(ensemble_manifest) if ensemble_manifest else None,
        "alignment_checkpoint": str(alignment_checkpoint) if alignment_checkpoint else None,
        "candidate_generator": generator.generator_name,
        "structure_alignment": "learned_w1" if alignment else "rule_proxy",
        "planner": planner.planner_name,
        "planning_config": config["planning"],
        "metrics": metrics,
        "acceptance": acceptance,
        "interpretation_limits": [
            "The held-out benchmark measures decision consistency and model-predicted counterfactuals, not live WebArena task success.",
            "Alternative rollout outcomes remain model predictions; a separate paired dataset provides observed factual/counterfactual outcomes for 100 initial states.",
            "The deterministic AXTree generator remains the planner default; a separate RTX 4090 ablation binds local Qwen2.5-3B-Instruct as a constrained semantic selector.",
            "The P1 test split contains observed severe_failure positives, so the severe-failure risk head is now evaluated rather than omitted.",
        ],
        "examples": examples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if acceptance["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
