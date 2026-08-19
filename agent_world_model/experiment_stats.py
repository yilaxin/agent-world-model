"""Paired statistics for frozen online task manifests."""

from __future__ import annotations

import random
import statistics
from typing import Any, Mapping, Sequence


def bootstrap_success_rate(
    values: Sequence[float], *, samples: int = 5000, seed: int = 2027
) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choice(values) for _ in values) for _ in range(samples)
    )
    return [means[int(0.025 * samples)], means[min(samples - 1, int(0.975 * samples))]]


def compare_success_rates(
    baseline: Mapping[str, float],
    candidate: Mapping[str, float],
    *,
    samples: int = 5000,
    seed: int = 2027,
) -> dict[str, Any]:
    keys = sorted(set(baseline) & set(candidate))
    if not keys:
        raise ValueError("baseline and candidate have no paired tasks")
    base_values = [float(baseline[key]) for key in keys]
    candidate_values = [float(candidate[key]) for key in keys]
    differences = [right - left for left, right in zip(base_values, candidate_values)]
    baseline_rate = statistics.fmean(base_values)
    candidate_rate = statistics.fmean(candidate_values)
    rng = random.Random(seed)
    boot = sorted(
        statistics.fmean(rng.choice(differences) for _ in differences)
        for _ in range(samples)
    )
    return {
        "paired_task_count": len(keys),
        "baseline_success_rate": baseline_rate,
        "candidate_success_rate": candidate_rate,
        "baseline_success_rate_95ci": bootstrap_success_rate(
            base_values, samples=samples, seed=seed
        ),
        "candidate_success_rate_95ci": bootstrap_success_rate(
            candidate_values, samples=samples, seed=seed + 1
        ),
        "absolute_improvement_points": 100.0 * (candidate_rate - baseline_rate),
        "absolute_improvement_95ci_points": [
            100.0 * boot[int(0.025 * samples)],
            100.0 * boot[min(samples - 1, int(0.975 * samples))],
        ],
        "relative_improvement": (
            (candidate_rate - baseline_rate) / baseline_rate
            if baseline_rate > 0
            else None
        ),
        "baseline_only_success": sum(left > right for left, right in zip(base_values, candidate_values)),
        "candidate_only_success": sum(right > left for left, right in zip(base_values, candidate_values)),
    }
