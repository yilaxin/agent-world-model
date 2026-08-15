"""Decision-regret feedback priorities and fixed-budget replay views."""

from __future__ import annotations

import copy
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .counterfactual import build_counterfactual_pairs, observed_utility


FEEDBACK_COMPONENTS = ("regret", "rank_flip", "stall", "struct_error")


@dataclass(frozen=True)
class FeedbackPriorityConfig:
    regret: float = 1.0
    rank_flip: float = 1.0
    stall: float = 0.75
    struct_error: float = 0.75
    uniform_fraction: float = 0.25
    maximum_weight: float = 4.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def robust_scale(values: Sequence[float]) -> list[float]:
    """Map a non-negative signal to [0, 1] using its train-only 95th percentile."""

    ceiling = max(1e-8, _percentile(values, 0.95))
    return [min(1.0, max(0.0, float(value)) / ceiling) for value in values]


def feedback_components(
    records: Sequence[Mapping[str, Any]],
    *,
    predicted_scores: Mapping[str, float],
    prediction_errors: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Annotate executed transitions with decision-impact feedback signals."""

    result: dict[str, dict[str, Any]] = {
        str(record["example_id"]): {
            "example_id": str(record["example_id"]),
            "prediction_error": float(prediction_errors.get(str(record["example_id"]), 0.0)),
            "regret": 0.0,
            "rank_flip": 0.0,
            "stall": float(record["risks"].get("stalled", 0.0)),
            "struct_error": float(
                bool(record["task_signals"].get("invalid_action", 0.0))
                or bool(record["risks"].get("goal_deviation", 0.0))
                or record.get("metadata", {}).get("intervention_type")
                in {"hard_wrong_target", "wrong_action_type", "nonexistent_target"}
            ),
            "pair_id": record.get("metadata", {}).get("counterfactual_pair_id"),
        }
        for record in records
    }
    for pair in build_counterfactual_pairs(records):
        rows = [pair["left"], pair["right"]]
        utilities = [float(pair["left_utility"]), float(pair["right_utility"])]
        scores = [
            float(predicted_scores.get(str(row["example_id"]), 0.0)) for row in rows
        ]
        best_actual = max(range(2), key=utilities.__getitem__)
        best_predicted = max(range(2), key=scores.__getitem__)
        flip = float(best_actual != best_predicted)
        best_utility = utilities[best_actual]
        for index, row in enumerate(rows):
            item = result[str(row["example_id"])]
            item["regret"] = max(0.0, best_utility - utilities[index])
            item["rank_flip"] = flip
    return [result[str(record["example_id"])] for record in records]


def priority_values(
    feedback: Sequence[Mapping[str, Any]],
    *,
    config: FeedbackPriorityConfig | None = None,
    omitted_components: Sequence[str] = (),
) -> list[float]:
    config = config or FeedbackPriorityConfig()
    omitted = set(omitted_components)
    scaled = {
        name: robust_scale([float(row[name]) for row in feedback])
        for name in FEEDBACK_COMPONENTS
    }
    raw: list[float] = []
    for index in range(len(feedback)):
        raw.append(
            sum(
                float(getattr(config, name)) * scaled[name][index]
                for name in FEEDBACK_COMPONENTS
                if name not in omitted
            )
        )
    return robust_scale(raw)


def replay_weights(
    feedback: Sequence[Mapping[str, Any]],
    *,
    strategy: str,
    config: FeedbackPriorityConfig | None = None,
    omitted_components: Sequence[str] = (),
) -> list[float]:
    """Return mean-one weights, preserving an explicit uniform replay fraction."""

    config = config or FeedbackPriorityConfig()
    if strategy == "uniform":
        return [1.0] * len(feedback)
    if strategy == "prediction_error":
        signal = robust_scale([float(row["prediction_error"]) for row in feedback])
    elif strategy == "priority":
        signal = priority_values(
            feedback, config=config, omitted_components=omitted_components
        )
    else:
        raise ValueError(f"unknown replay strategy: {strategy}")
    floor = min(1.0, max(0.0, config.uniform_fraction))
    raw = [floor + (1.0 - floor) * value for value in signal]
    mean = statistics.fmean(raw) if raw else 1.0
    normalized = [min(config.maximum_weight, value / max(mean, 1e-8)) for value in raw]
    correction = statistics.fmean(normalized) if normalized else 1.0
    return [value / max(correction, 1e-8) for value in normalized]


def build_replay_view(
    records: Sequence[Mapping[str, Any]],
    feedback: Sequence[Mapping[str, Any]],
    *,
    strategy: str,
    config: FeedbackPriorityConfig | None = None,
    omitted_components: Sequence[str] = (),
) -> list[dict[str, Any]]:
    if len(records) != len(feedback):
        raise ValueError("records and feedback must have identical lengths")
    weights = replay_weights(
        feedback,
        strategy=strategy,
        config=config,
        omitted_components=omitted_components,
    )
    result: list[dict[str, Any]] = []
    for record, signals, weight in zip(records, feedback, weights):
        copied = copy.deepcopy(record)
        metadata = copied.setdefault("metadata", {})
        metadata["phase4_replay_strategy"] = strategy
        metadata["phase4_replay_weight"] = float(weight)
        metadata["phase4_feedback"] = {
            name: float(signals[name])
            for name in ("prediction_error", *FEEDBACK_COMPONENTS)
        }
        metadata["phase4_omitted_components"] = list(omitted_components)
        result.append(copied)
    return result


def feedback_summary(feedback: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_pair: dict[str, int] = defaultdict(int)
    for row in feedback:
        if row.get("pair_id"):
            by_pair[str(row["pair_id"])] += 1
    result: dict[str, Any] = {
        "example_count": len(feedback),
        "complete_observed_pair_count": sum(count == 2 for count in by_pair.values()),
    }
    for name in ("prediction_error", *FEEDBACK_COMPONENTS):
        values = [float(row[name]) for row in feedback]
        result[name] = {
            "mean": statistics.fmean(values) if values else 0.0,
            "p95": _percentile(values, 0.95),
            "positive_count": sum(value > 0 for value in values),
        }
    return result


def pairwise_decision_metrics(
    records: Sequence[Mapping[str, Any]],
    predicted_scores: Mapping[str, float],
) -> dict[str, float | int]:
    correctness: list[float] = []
    regrets: list[float] = []
    for pair in build_counterfactual_pairs(records):
        rows = [pair["left"], pair["right"]]
        utilities = [float(pair["left_utility"]), float(pair["right_utility"])]
        scores = [float(predicted_scores[str(row["example_id"])]) for row in rows]
        predicted = max(range(2), key=scores.__getitem__)
        actual = max(range(2), key=utilities.__getitem__)
        correctness.append(float(predicted == actual))
        regrets.append(max(utilities) - utilities[predicted])
    accuracy = statistics.fmean(correctness) if correctness else 0.0
    return {
        "informative_pair_count": len(correctness),
        "pairwise_accuracy": accuracy,
        "rank_flip_rate": 1.0 - accuracy,
        "mean_decision_regret": statistics.fmean(regrets) if regrets else 0.0,
    }
