from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "diff_failure_attribution.py")


def load_module():
    spec = importlib.util.spec_from_file_location("diff_failure_attribution", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(
    site: str,
    task: int,
    seed: int,
    category: str,
    mode: str = "reactive",
    guard: str = "off",
) -> dict:
    return {
        "site": site,
        "mode": mode,
        "guard": guard,
        "task_id": str(task),
        "seed": str(seed),
        "success": category == "success",
        "category": "success" if category == "success" else category,
        "reasons": [f"{category} reason"],
        "signals": {"goal": f"goal for {site} {task}"},
        "trajectory_path": f"/tmp/{site}_{task}_{seed}.jsonl",
    }


def test_transition_matrix_and_category_deltas() -> None:
    module = load_module()
    baseline = [
        record("gitlab", 1, 0, "loop_stall"),
        record("gitlab", 2, 0, "loop_stall"),
        record("gitlab", 3, 0, "loop_stall"),
        record("gitlab", 4, 0, "wrong_route"),
        record("gitlab", 5, 0, "success"),
        record("gitlab", 6, 0, "success"),
    ]
    candidate = [
        record("gitlab", 1, 0, "success"),          # fixed
        record("gitlab", 2, 0, "success"),          # fixed
        record("gitlab", 3, 0, "loop_stall"),       # unchanged
        record("gitlab", 4, 0, "wrong_route"),      # unchanged
        record("gitlab", 5, 0, "budget_exhausted"), # regressed
        record("gitlab", 6, 0, "success"),          # still success
    ]
    result = module.compare(baseline, candidate, targets=["loop_stall"])
    assert result["paired_units"] == 6
    assert result["transitions"]["fixed"] == 2
    assert result["transitions"]["regressed"] == 1
    assert result["transitions"]["unchanged_failure"] == 2
    assert result["transitions"]["still_success"] == 1
    deltas = {entry["category"]: entry for entry in result["category_deltas"]}
    assert deltas["loop_stall"]["baseline"] == 3
    assert deltas["loop_stall"]["candidate"] == 1
    assert deltas["loop_stall"]["is_target"] is True
    # Two fixes against one regression still raises the paired success count,
    # so the gate passes; the regression is reported separately.
    assert result["paired_base_summary"]["successes"] == 2
    assert result["paired_candidate_summary"]["successes"] == 3
    assert result["regressed_examples"][0]["task_id"] == "5"
    assert result["verdict"] == "PASS"


def test_recategorised_flow_is_reported() -> None:
    module = load_module()
    baseline = [record("shopping", 10, 0, "budget_exhausted")]
    candidate = [record("shopping", 10, 0, "form_or_search_incomplete")]
    result = module.compare(baseline, candidate, targets=["budget_exhausted"])
    assert result["transitions"]["recategorised"] == 1
    assert result["recategorised_flows"][0]["from"] == "budget_exhausted"
    assert result["recategorised_flows"][0]["to"] == "form_or_search_incomplete"
    # Budget exhausted dropped to 0, and the new category has no baseline count.
    assert result["verdict"] == "PASS"


def test_growth_rule_blocks_pass_when_another_category_inflates() -> None:
    module = load_module()
    baseline = [
        record("gitlab", 5, 0, "loop_stall"),
        record("gitlab", 2, 0, "wrong_route"),
        record("gitlab", 3, 0, "wrong_route"),
        record("gitlab", 4, 0, "wrong_route"),
        record("gitlab", 1, 0, "wrong_route"),
    ]
    candidate = [
        record("gitlab", 1, 0, "success"),
        record("gitlab", 2, 0, "wrong_route"),
        record("gitlab", 3, 0, "loop_stall"),
        record("gitlab", 4, 0, "loop_stall"),
        record("gitlab", 5, 0, "loop_stall"),
    ]
    result = module.compare(baseline, candidate, targets=["wrong_route"])
    growth = [entry for entry in result["decisions"] if entry["rule"].startswith("other_")]
    assert any(not entry["passed"] for entry in growth)
    assert result["verdict"] == "FAIL"


def test_new_failure_mode_is_blocked_beyond_allowance() -> None:
    module = load_module()
    baseline = [record("gitlab", task, 0, "loop_stall") for task in range(1, 7)]
    candidate = [record("gitlab", task, 0, "success") for task in range(1, 5)]
    candidate.append(record("gitlab", 5, 0, "action_execution"))
    candidate.append(record("gitlab", 6, 0, "action_execution"))
    result = module.compare(
        baseline,
        candidate,
        targets=["loop_stall"],
        max_new_category_episodes=1,
    )
    new_rules = [entry for entry in result["decisions"] if entry["rule"].startswith("new_")]
    assert new_rules and not new_rules[0]["passed"]
    assert result["verdict"] == "FAIL"


def test_only_shared_keys_are_paired() -> None:
    module = load_module()
    baseline = [record("gitlab", 1, 0, "loop_stall"), record("gitlab", 2, 0, "loop_stall")]
    candidate = [record("gitlab", 1, 0, "success"), record("gitlab", 3, 0, "loop_stall")]
    result = module.compare(baseline, candidate)
    assert result["paired_units"] == 1
    assert result["only_in_baseline_count"] == 1
    assert result["only_in_candidate_count"] == 1
    assert result["transitions"]["fixed"] == 1


def test_markdown_renders_verdict_and_tables() -> None:
    module = load_module()
    baseline = [record("gitlab", 1, 0, "loop_stall")]
    candidate = [record("gitlab", 1, 0, "success")]
    result = module.compare(baseline, candidate, targets=["loop_stall"])
    markdown = module.render_markdown(result, max_examples=3)
    assert "判定：PASS" in markdown
    assert "配对迁移" in markdown
    assert "修复样本" in markdown
