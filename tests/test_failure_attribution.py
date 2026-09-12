from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "attribute_webarena_failures.py"


def load_module():
    spec = importlib.util.spec_from_file_location("failure_attribution", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_row(
    step: int,
    action: str,
    url: str,
    goal: str,
    error: str = "",
    reward: float = 0.0,
    features: dict | None = None,
    target_name: str = "",
) -> dict:
    candidate = None
    if features is not None:
        candidate = {
            "action": action,
            "target_name": target_name,
            "source": "structure",
            "metadata": {"structure_components": {"feature_values": features}},
        }
    return {
        "step_index": step,
        "action": action,
        "reward": reward,
        "state": {"url": url, "goal": goal},
        "next_state": {"url": url, "last_action_error": error},
        "decision": {"mode": "planned", "candidates": [candidate] if candidate else []},
    }


def test_parse_report_name_handles_round_and_site_shapes() -> None:
    module = load_module()
    round4 = module.parse_report_name(
        Path("webarena_p0_round4_holdout_gitlab_world-model_guard_off.json")
    )
    assert round4 == ("round4", "gitlab", "world-model", "off")
    round1 = module.parse_report_name(
        Path("webarena_p0_holdout_shopping_reactive_guard_on.json")
    )
    assert round1 == ("round1", "shopping", "reactive", "on")


def test_parse_report_name_handles_development_reports() -> None:
    module = load_module()
    plain = module.parse_report_name(Path("webarena_p0_round3_dev_gitlab_reactive.json"))
    assert plain == ("round3dev", "gitlab", "reactive", "off")
    versioned = module.parse_report_name(
        Path("webarena_p0_round3_dev_v2_shopping_world-model.json")
    )
    assert versioned == ("round3dev-v2", "shopping", "world-model", "off")
    shipped = module.parse_report_name(Path("webarena_r3dev_v7_gitlab_reactive.json"))
    assert shipped == ("r3dev-v7", "gitlab", "reactive", "off")


def test_expected_fragments_ignores_project_names_inside_words() -> None:
    module = load_module()
    commit_goal = "How many commits did Eric and Kilian make to a11yproject on 1/3/2023?"
    assert module.expected_fragments("gitlab", commit_goal) == ("/commits", "/-/commits")
    create_goal = "Set up a new, empty repository with the name webagent?"
    assert module.expected_fragments("gitlab", create_goal) == ("/projects/new",)


def test_repeated_clicks_without_progress_is_loop_stall() -> None:
    module = load_module()
    rows = [
        make_row(index, 'click("55", "left")', "http://localhost:8023/", "Do the thing")
        for index in range(12)
    ]
    signals = module.analyse(rows, {"site": "gitlab", "steps": 12})
    category, reasons = module.classify(signals)
    assert category == "loop_stall"
    assert reasons


def test_glossary_page_without_submission_is_wrong_route() -> None:
    module = load_module()
    goal = "Create a new issue about dark mode"
    rows = [
        make_row(index, f'click("h{index}", "left")', f"http://localhost:8023/help/page{index}", goal)
        for index in range(8)
    ]
    signals = module.analyse(rows, {"site": "gitlab", "steps": 12})
    category, _ = module.classify(signals)
    assert category == "wrong_route"


def test_reaching_issue_list_without_answer_is_missing_termination() -> None:
    module = load_module()
    goal = "List all opened issues requesting new features"
    rows = [
        make_row(0, 'click("3", "left")', "http://localhost:8023/dashboard", goal),
        make_row(1, 'click("4", "left")', "http://localhost:8023/dashboard/issues", goal),
    ]
    signals = module.analyse(rows, {"site": "gitlab", "steps": 12})
    category, _ = module.classify(signals)
    assert category == "missing_termination"


def test_form_page_without_typing_is_form_incomplete() -> None:
    module = load_module()
    goal = "Set up a new, empty repository with the name webagent"
    rows = [
        make_row(0, 'click("7", "left")', "http://localhost:8023/projects/new", goal),
        make_row(1, 'click("8", "left")', "http://localhost:8023/projects/new", goal),
    ]
    signals = module.analyse(rows, {"site": "gitlab", "steps": 12})
    category, _ = module.classify(signals)
    assert category == "form_or_search_incomplete"


def test_semantically_unrelated_candidates_are_candidate_missing() -> None:
    module = load_module()
    goal = "Toggle the third setting on the page"
    unrelated = {"semantic_overlap": 0.0, "intent_compatible": 0.0, "role_compatible": 0.0}
    rows = [
        make_row(
            index,
            f'click("a{index}", "left")',
            "http://localhost:8023/settings",
            goal,
            features=unrelated,
            target_name=f"control{index}",
        )
        for index in range(8)
    ]
    signals = module.analyse(rows, {"site": "gitlab", "steps": 12})
    category, _ = module.classify(signals)
    assert category == "candidate_missing"
