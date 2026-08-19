"""Dependency-light metrics for every phase-two prediction head."""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence


def _values(items: Iterable[float]) -> list[float]:
    return [float(item) for item in items]


def regression_metrics(
    targets: Iterable[float], predictions: Iterable[float]
) -> dict[str, float]:
    truth, predicted = _values(targets), _values(predictions)
    if len(truth) != len(predicted) or not truth:
        raise ValueError("targets and predictions must be non-empty and equal length")
    errors = [estimate - actual for actual, estimate in zip(truth, predicted)]
    return {
        "mae": sum(abs(item) for item in errors) / len(errors),
        "mse": sum(item * item for item in errors) / len(errors),
        "rmse": math.sqrt(sum(item * item for item in errors) / len(errors)),
    }


def expected_calibration_error(
    targets: Iterable[float],
    probabilities: Iterable[float],
    *,
    bins: int = 10,
) -> float:
    truth, predicted = _values(targets), _values(probabilities)
    if len(truth) != len(predicted) or not truth:
        raise ValueError("targets and probabilities must be non-empty and equal length")
    total = len(truth)
    result = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        members = [
            offset
            for offset, probability in enumerate(predicted)
            if lower <= probability < upper
            or (index == bins - 1 and probability == upper)
        ]
        if not members:
            continue
        accuracy = sum(truth[item] for item in members) / len(members)
        confidence = sum(predicted[item] for item in members) / len(members)
        result += len(members) / total * abs(accuracy - confidence)
    return result


def binary_negative_log_likelihood(
    targets: Iterable[float], probabilities: Iterable[float]
) -> float:
    """Mean Bernoulli negative log likelihood with numerically safe clipping."""

    truth, predicted = _values(targets), _values(probabilities)
    if len(truth) != len(predicted) or not truth:
        raise ValueError("targets and probabilities must be non-empty and equal length")
    epsilon = 1e-7
    return -sum(
        target * math.log(min(1.0 - epsilon, max(epsilon, probability)))
        + (1.0 - target)
        * math.log(min(1.0 - epsilon, max(epsilon, 1.0 - probability)))
        for target, probability in zip(truth, predicted)
    ) / len(truth)


def coverage_risk_curve(
    targets: Iterable[float],
    probabilities: Iterable[float],
    *,
    coverages: Sequence[float] = (0.25, 0.50, 0.75, 1.0),
) -> dict[str, object]:
    """Selective classification risk at fixed coverage levels.

    Confidence is the calibrated distance from the decision boundary.  This is
    intentionally dependency-light and makes the phase-three fallback policy
    auditable even when an ensemble is not available.
    """

    truth, predicted = _values(targets), _values(probabilities)
    if len(truth) != len(predicted) or not truth:
        raise ValueError("targets and probabilities must be non-empty and equal length")
    if any(not 0.0 < coverage <= 1.0 for coverage in coverages):
        raise ValueError("coverages must be in (0, 1]")
    ranked = sorted(
        zip(truth, predicted),
        key=lambda item: abs(item[1] - 0.5),
        reverse=True,
    )
    points: list[dict[str, float]] = []
    for coverage in coverages:
        count = max(1, math.ceil(len(ranked) * coverage))
        selected = ranked[:count]
        errors = sum((probability >= 0.5) != (target >= 0.5) for target, probability in selected)
        points.append(
            {
                "coverage": float(count / len(ranked)),
                "risk": float(errors / count),
                "count": float(count),
            }
        )
    return {
        "points": points,
        "aurc": sum(point["risk"] for point in points) / len(points),
    }


def binary_metrics(
    targets: Iterable[float],
    probabilities: Iterable[float],
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    truth, predicted = _values(targets), _values(probabilities)
    if len(truth) != len(predicted) or not truth:
        raise ValueError("targets and probabilities must be non-empty and equal length")
    labels = [value >= threshold for value in predicted]
    actual = [value >= 0.5 for value in truth]
    tp = sum(left and right for left, right in zip(actual, labels))
    fp = sum((not left) and right for left, right in zip(actual, labels))
    fn = sum(left and (not right) for left, right in zip(actual, labels))
    tn = len(actual) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    positive_scores = [
        probability for value, probability in zip(actual, predicted) if value
    ]
    negative_scores = [
        probability for value, probability in zip(actual, predicted) if not value
    ]
    if positive_scores and negative_scores:
        wins = sum(
            1.0 if positive > negative else 0.5 if positive == negative else 0.0
            for positive in positive_scores
            for negative in negative_scores
        )
        auroc = wins / (len(positive_scores) * len(negative_scores))
    else:
        auroc = 0.0
    ranked = sorted(zip(predicted, actual), key=lambda item: item[0], reverse=True)
    positive_seen = 0
    precision_at_positive = 0.0
    for rank, (_, is_positive) in enumerate(ranked, start=1):
        if is_positive:
            positive_seen += 1
            precision_at_positive += positive_seen / rank
    auprc = precision_at_positive / len(positive_scores) if positive_scores else 0.0
    return {
        "accuracy": (tp + tn) / len(actual),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auroc": auroc,
        "auprc": auprc,
        "brier": sum(
            (probability - target) ** 2
            for target, probability in zip(truth, predicted)
        )
        / len(truth),
        "ece": expected_calibration_error(truth, predicted),
        "nll": binary_negative_log_likelihood(truth, predicted),
        "coverage_risk": coverage_risk_curve(truth, predicted),
        "support_positive": float(sum(actual)),
        "support_negative": float(len(actual) - sum(actual)),
    }


def multilabel_metrics(
    targets: Sequence[Sequence[float]],
    probabilities: Sequence[Sequence[float]],
    names: Sequence[str],
) -> dict[str, object]:
    if len(targets) != len(probabilities) or not targets:
        raise ValueError("targets and probabilities must be non-empty and equal length")
    per_label = {
        name: binary_metrics(
            (row[index] for row in targets),
            (row[index] for row in probabilities),
        )
        for index, name in enumerate(names)
    }
    supported = [
        value
        for value in per_label.values()
        if value["support_positive"] > 0 and value["support_negative"] > 0
    ]
    return {
        "per_label": per_label,
        "macro_f1": sum(value["f1"] for value in per_label.values()) / len(per_label),
        "macro_f1_supported": (
            sum(value["f1"] for value in supported) / len(supported)
            if supported
            else 0.0
        ),
        "macro_auroc_supported": (
            sum(value["auroc"] for value in supported) / len(supported)
            if supported
            else 0.0
        ),
        "macro_auprc_supported": (
            sum(value["auprc"] for value in supported) / len(supported)
            if supported
            else 0.0
        ),
        "macro_ece": sum(value["ece"] for value in per_label.values()) / len(per_label),
        "macro_brier": sum(value["brier"] for value in per_label.values())
        / len(per_label),
        "macro_nll": sum(value["nll"] for value in per_label.values())
        / len(per_label),
        "macro_aurc": sum(
            value["coverage_risk"]["aurc"] for value in per_label.values()
        )
        / len(per_label),
        "supported_label_count": len(supported),
    }


def evaluate_thresholds(
    metrics: Mapping[str, object],
    thresholds: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate dotted metric paths, e.g. ``risk.macro_f1``."""

    results: dict[str, dict[str, object]] = {}
    for path, rule in thresholds.items():
        value: object = metrics
        for part in path.split("."):
            if not isinstance(value, Mapping) or part not in value:
                raise KeyError(f"Missing metric path: {path}")
            value = value[part]
        if isinstance(rule, Mapping):
            operator = str(rule.get("op", ">="))
            target = float(rule["value"])
        else:
            operator = ">="
            target = float(rule)
        actual = float(value)
        if operator == ">=":
            passed = actual >= target
        elif operator == "<=":
            passed = actual <= target
        else:
            raise ValueError(f"Unsupported threshold operator: {operator}")
        results[path] = {
            "actual": actual,
            "operator": operator,
            "target": target,
            "passed": passed,
        }
    return {
        "passed": all(item["passed"] for item in results.values()),
        "checks": results,
    }
