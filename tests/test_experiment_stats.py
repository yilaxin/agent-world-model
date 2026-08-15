from agent_world_model.experiment_stats import compare_success_rates


def test_paired_success_comparison_reports_both_improvement_units() -> None:
    result = compare_success_rates(
        {"a": 0, "b": 1, "c": 0, "d": 1},
        {"a": 1, "b": 1, "c": 0, "d": 1},
        samples=200,
    )
    assert result["baseline_success_rate"] == 0.5
    assert result["candidate_success_rate"] == 0.75
    assert result["absolute_improvement_points"] == 25.0
    assert result["relative_improvement"] == 0.5
    assert result["candidate_only_success"] == 1
