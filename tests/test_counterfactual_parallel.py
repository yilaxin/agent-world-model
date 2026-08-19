from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "collect_phase2_counterfactuals_parallel.py"
)
SPEC = importlib.util.spec_from_file_location("counterfactual_parallel", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_split_tasks_is_complete_and_disjoint() -> None:
    tasks = [f"task-{index}" for index in range(10)]
    shards = MODULE.split_tasks(tasks, 4)

    assert [len(shard) for shard in shards] == [3, 3, 2, 2]
    assert sorted(task for shard in shards for task in shard) == tasks


def test_aggregate_reports_sums_observed_results() -> None:
    base = {
        "planned_pairs": 2,
        "valid_pairs": 2,
        "informative_pairs": 1,
        "failed_pairs": 0,
        "transition_count": 4,
        "counterfactual_invalid_action_positives": 1,
        "counterfactual_severe_failure_positives": 1,
        "counterfactual_successes": 0,
        "task_count": 1,
        "strategies": ["missing_target"],
        "strategy_counts": {"missing_target": 2},
        "observed_outcomes_only": True,
        "rows": [{"pair_id": "a"}],
        "failures": [],
    }

    aggregate = MODULE.aggregate_reports([base, base])

    assert aggregate["planned_pairs"] == 4
    assert aggregate["valid_pairs"] == 4
    assert aggregate["informative_pairs"] == 2
    assert aggregate["transition_count"] == 8
    assert aggregate["failure_rate"] == 0.0
    assert aggregate["strategy_counts"] == {"missing_target": 4}
    assert aggregate["shard_count"] == 2
    assert MODULE.quality_gate(
        aggregate,
        min_valid_pairs=4,
        max_failure_rate=0.05,
    )
