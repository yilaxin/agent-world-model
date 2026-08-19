"""Observed counterfactual pairing and utility helpers.

The helpers in this module deliberately operate only on transitions that were
executed in the environment.  They are shared by dataset audits, pairwise
training and held-out ranking evaluation so that all three stages use exactly
the same definition of an informative pair.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence


def _section(record: Mapping[str, Any] | Any, name: str) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return record.get(name, {})
    return getattr(record, name, {})


def _metadata(record: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return record.get("metadata", {})
    return getattr(record, "metadata", {})


def observed_utility(record: Mapping[str, Any] | Any) -> float:
    """Return the project-wide realised utility for one observed transition."""

    signals = _section(record, "task_signals")
    risks = _section(record, "risks")
    return (
        2.0 * float(risks.get("success", 0.0))
        + float(signals.get("progress", 0.0))
        + 0.5 * float(signals.get("reward", 0.0))
        - float(signals.get("invalid_action", 0.0))
        - 0.75 * float(risks.get("stalled", 0.0))
        - float(risks.get("goal_deviation", 0.0))
        - 2.0 * float(risks.get("severe_failure", 0.0))
    )


def build_counterfactual_pairs(
    records: Sequence[Mapping[str, Any] | Any],
    *,
    minimum_utility_gap: float = 0.05,
    include_ties: bool = False,
) -> list[dict[str, Any]]:
    """Build leakage-safe factual/counterfactual pairs from observed records."""

    groups: dict[str, list[Mapping[str, Any] | Any]] = defaultdict(list)
    for record in records:
        metadata = _metadata(record)
        pair_id = str(metadata.get("counterfactual_pair_id", ""))
        if pair_id and bool(metadata.get("observed_in_environment")):
            groups[pair_id].append(record)

    pairs: list[dict[str, Any]] = []
    for pair_id, rows in sorted(groups.items()):
        if len(rows) != 2:
            continue
        roles = {str(_metadata(row).get("counterfactual_role", "")) for row in rows}
        if roles != {"factual", "counterfactual"}:
            continue
        initial_states = {
            str(_metadata(row).get("initial_state_id", "")) for row in rows
        }
        if len(initial_states) != 1 or "" in initial_states:
            continue
        ordered = sorted(
            rows,
            key=lambda row: str(_metadata(row).get("counterfactual_role"))
            != "factual",
        )
        utilities = [observed_utility(row) for row in ordered]
        gap = utilities[0] - utilities[1]
        informative = abs(gap) >= minimum_utility_gap
        if not informative and not include_ties:
            continue
        pairs.append(
            {
                "pair_id": pair_id,
                "left": ordered[0],
                "right": ordered[1],
                "left_utility": utilities[0],
                "right_utility": utilities[1],
                "utility_gap": gap,
                "informative": informative,
                "intervention_type": str(
                    _metadata(ordered[1]).get("intervention_type", "unspecified")
                ),
            }
        )
    return pairs


def counterfactual_pair_summary(
    records: Sequence[Mapping[str, Any] | Any],
    *,
    minimum_utility_gap: float = 0.05,
) -> dict[str, Any]:
    all_pairs = build_counterfactual_pairs(
        records,
        minimum_utility_gap=minimum_utility_gap,
        include_ties=True,
    )
    informative = [pair for pair in all_pairs if pair["informative"]]
    intervention_counts: dict[str, int] = defaultdict(int)
    for pair in all_pairs:
        intervention_counts[str(pair["intervention_type"])] += 1
    return {
        "observed_pair_count": len(all_pairs),
        "informative_pair_count": len(informative),
        "tied_or_near_tied_pair_count": len(all_pairs) - len(informative),
        "informative_rate": len(informative) / max(1, len(all_pairs)),
        "intervention_type_counts": dict(sorted(intervention_counts.items())),
        "minimum_utility_gap": minimum_utility_gap,
    }
