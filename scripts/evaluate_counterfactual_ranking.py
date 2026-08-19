#!/usr/bin/env python3
"""Evaluate W0/W3 ranking on observed same-state counterfactual pairs."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_ensemble import EnsembleWorldModelPredictor  # noqa: E402
from agent_world_model.counterfactual import observed_utility  # noqa: E402
from agent_world_model.phase2_training import WorldModelPredictor, load_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ensemble-manifest",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "phase2" / "world_model_ensemble_p1.json",
    )
    parser.add_argument("--single-checkpoint", type=Path)
    parser.add_argument("--dataset-dir", type=Path, default=PROJECT_ROOT / "data" / "phase2_p1")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--minimum-utility-gap", type=float, default=0.05)
    parser.add_argument("--minimum-informative-test-pairs", type=int, default=200)
    parser.add_argument("--noninferiority-margin", type=float, default=0.02)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase3_counterfactual_ranking_gpu.json",
    )
    return parser.parse_args()


def bootstrap_ci(values: Sequence[float], *, samples: int = 2000, seed: int = 2026) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choice(values) for _ in values) for _ in range(samples)
    )
    return [means[int(0.025 * samples)], means[min(samples - 1, int(0.975 * samples))]]


def paired_bootstrap_difference(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    samples: int = 5000,
    seed: int = 2026,
) -> dict[str, Any]:
    pair_ids = sorted(set(baseline) & set(candidate))
    if not pair_ids:
        return {"pair_count": 0, "mean_difference": 0.0, "difference_95ci": [0.0, 0.0]}
    differences = [candidate[pair_id] - baseline[pair_id] for pair_id in pair_ids]
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choice(differences) for _ in differences)
        for _ in range(samples)
    )
    single_only = sum(
        baseline[pair_id] > candidate[pair_id] for pair_id in pair_ids
    )
    ensemble_only = sum(
        candidate[pair_id] > baseline[pair_id] for pair_id in pair_ids
    )
    return {
        "pair_count": len(pair_ids),
        "mean_difference": statistics.fmean(differences),
        "difference_95ci": [
            means[int(0.025 * samples)],
            means[min(samples - 1, int(0.975 * samples))],
        ],
        "discordant_single_only_correct": single_only,
        "discordant_ensemble_only_correct": ensemble_only,
    }


def ndcg_for_pair(actual: list[float], predicted_order: list[int]) -> float:
    minimum = min(actual)
    gains = [value - minimum for value in actual]
    ideal = sorted(gains, reverse=True)
    denominator = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal))
    if denominator <= 0:
        return 1.0
    numerator = sum(gains[item] / math.log2(index + 2) for index, item in enumerate(predicted_order))
    return numerator / denominator


def evaluate(
    predictor: Any,
    records: list[dict[str, Any]],
    *,
    minimum_utility_gap: float = 0.05,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        pair_id = record.get("metadata", {}).get("counterfactual_pair_id")
        if pair_id and record.get("metadata", {}).get("observed_in_environment"):
            groups[str(pair_id)].append(record)
    correctness: list[float] = []
    regrets: list[float] = []
    ndcgs: list[float] = []
    examples: list[dict[str, Any]] = []
    correctness_by_pair: dict[str, float] = {}
    state_mismatch = 0
    tied_outcomes = 0
    for pair_id, rows in sorted(groups.items()):
        if len(rows) != 2:
            continue
        if rows[0].get("metadata", {}).get("initial_state_id") != rows[1].get("metadata", {}).get("initial_state_id"):
            state_mismatch += 1
            continue
        actual = [observed_utility(row) for row in rows]
        if abs(actual[0] - actual[1]) < minimum_utility_gap:
            tied_outcomes += 1
            continue
        actions = [row["action"] for row in rows]
        ranked = predictor.rank_actions(rows[0]["state_vector"], actions)
        score_by_action = {row["action"]: float(row["score"]) for row in ranked}
        predicted_order = sorted(range(2), key=lambda index: score_by_action[actions[index]], reverse=True)
        predicted = predicted_order[0]
        best = max(range(2), key=lambda index: actual[index])
        correctness.append(float(predicted == best))
        correctness_by_pair[pair_id] = float(predicted == best)
        regrets.append(max(actual) - actual[predicted])
        ndcgs.append(ndcg_for_pair(actual, predicted_order))
        if len(examples) < 12:
            examples.append(
                {
                    "pair_id": pair_id,
                    "actions": actions,
                    "actual_utility": actual,
                    "predicted_scores": [score_by_action[action] for action in actions],
                    "correct": predicted == best,
                }
            )
    return {
        "observed_pair_count": sum(len(rows) == 2 for rows in groups.values()),
        "informative_pair_count": len(correctness),
        "tied_outcome_pair_count": tied_outcomes,
        "state_mismatch_count": state_mismatch,
        "pairwise_accuracy": statistics.fmean(correctness) if correctness else 0.0,
        "pairwise_accuracy_95ci": bootstrap_ci(correctness),
        "rank_flip_rate": 1.0 - (statistics.fmean(correctness) if correctness else 0.0),
        "mean_decision_regret": statistics.fmean(regrets) if regrets else 0.0,
        "ndcg_at_2": statistics.fmean(ndcgs) if ndcgs else 0.0,
        "correctness_by_pair": correctness_by_pair,
        "examples": examples,
    }


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.ensemble_manifest.read_text(encoding="utf-8"))
    single_checkpoint = args.single_checkpoint or PROJECT_ROOT / manifest["champion_single_checkpoint"]
    models = {
        "selected_single": WorldModelPredictor(single_checkpoint, device=args.device),
        "calibrated_ensemble": EnsembleWorldModelPredictor(args.ensemble_manifest, device=args.device),
    }
    results: dict[str, Any] = {}
    for split in ("validation", "test"):
        rows = load_jsonl(args.dataset_dir / f"{split}.jsonl")
        results[split] = {
            name: evaluate(
                predictor,
                rows,
                minimum_utility_gap=args.minimum_utility_gap,
            )
            for name, predictor in models.items()
        }
    ensemble_test = results["test"]["calibrated_ensemble"]
    single_test = results["test"]["selected_single"]
    comparison = paired_bootstrap_difference(
        single_test["correctness_by_pair"],
        ensemble_test["correctness_by_pair"],
    )
    validation_single = results["validation"]["selected_single"]
    validation_ensemble = results["validation"]["calibrated_ensemble"]
    production_method = (
        "calibrated_ensemble"
        if (
            validation_ensemble["pairwise_accuracy"],
            validation_ensemble["ndcg_at_2"],
            -validation_ensemble["mean_decision_regret"],
        )
        >= (
            validation_single["pairwise_accuracy"],
            validation_single["ndcg_at_2"],
            -validation_single["mean_decision_regret"],
        )
        else "selected_single"
    )
    checks = {
        "minimum_informative_test_pairs": (
            ensemble_test["informative_pair_count"]
            >= args.minimum_informative_test_pairs
        ),
        "no_state_mismatch": ensemble_test["state_mismatch_count"] == 0,
        "ensemble_not_below_selected_single": ensemble_test["pairwise_accuracy"] >= single_test["pairwise_accuracy"],
        "ensemble_noninferior_95ci": (
            comparison["difference_95ci"][0] >= -args.noninferiority_margin
        ),
        "ensemble_ndcg_not_below_single": (
            ensemble_test["ndcg_at_2"] >= single_test["ndcg_at_2"]
        ),
        "ensemble_regret_not_above_single": (
            ensemble_test["mean_decision_regret"]
            <= single_test["mean_decision_regret"]
        ),
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ensemble_manifest": str(args.ensemble_manifest),
        "single_checkpoint": str(single_checkpoint),
        "actual_utility_definition": "2*success + progress + 0.5*reward - invalid - 0.75*stall - deviation - 2*severe_failure",
        "results": results,
        "paired_test_comparison": comparison,
        "production_method_selected_on_validation": production_method,
        "minimum_informative_test_pairs": args.minimum_informative_test_pairs,
        "minimum_utility_gap": args.minimum_utility_gap,
        "noninferiority_margin": args.noninferiority_margin,
        "acceptance": {"passed": all(checks.values()), "checks": checks},
        "interpretation_limit": "Only observed same-state pairs are used; tied or near-tied outcomes are excluded. Production fallback is selected on validation only.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
