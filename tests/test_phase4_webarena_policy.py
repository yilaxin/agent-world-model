from __future__ import annotations

import importlib.util
import unittest

from agent_world_model.phase3_candidates import AXTreeCandidateGenerator
from agent_world_model.reactive_agent import ReactiveAgent


def _reddit_state(goal: str) -> dict:
    return {
        "goal": goal,
        "url": "http://reddit.local/",
        "axtree": {
            "text": (
                "RootWebArea 'Postmill'\n"
                "  [54] searchbox 'Search query', clickable\n"
                "  [42] link 'Forums', clickable\n"
                "  [70] link 'space', clickable"
            )
        },
    }


def test_quoted_forum_name_is_extracted_for_reactive_policy() -> None:
    state = _reddit_state('Open a trending post on the forum "space" and subscribe.')
    decision = ReactiveAgent().decide(state)
    assert decision.action == 'click("70", "left")'


def test_quoted_forum_name_produces_task_query_candidate() -> None:
    state = _reddit_state('Open a trending post on the forum "space" and subscribe.')
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    assert any(row.action == 'fill("54", "space")' for row in candidates)


def test_filled_forum_query_uses_webarena_keyboard_action() -> None:
    state = _reddit_state('Open a trending post on the forum "space" and subscribe.')
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(
        state, ('fill("54", "space")',)
    )
    assert any(row.action == 'keyboard_press("Enter")' for row in candidates)


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_semantic_guard_avoids_recently_repeated_control() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = {
        "goal": "Open my most recent issues.",
        "axtree": {
            "text": (
                "RootWebArea 'GitLab'\n"
                "  [1] link 'Issues', clickable\n"
                "  [2] link 'Most recent issues', clickable"
            )
        },
    }
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    first = Phase3WorldModelAgent._semantic_goal_match(state["goal"], candidates)
    assert first is not None
    second = Phase3WorldModelAgent._semantic_goal_match(
        state["goal"], candidates, (first[0],)
    )
    assert second is not None
    assert second[0] != first[0]


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_interaction_guard_submits_site_search_after_fill() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = {
        "goal": 'Search for "usb wifi"',
        "axtree": {
            "text": (
                "RootWebArea 'Shop'\n"
                "  [386] combobox 'Search', value='usb wifi', clickable\n"
                "  [391] button 'Search', clickable"
            )
        },
    }
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(
        state, ('fill("386", "usb wifi")',)
    )
    guarded = Phase3WorldModelAgent._interaction_guard(
        state["goal"], candidates, ('fill("386", "usb wifi")',)
    )
    assert guarded is not None
    assert guarded[0] == 'click("391", "left")'


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_interaction_guard_fills_quoted_forum_before_semantic_clicks() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = _reddit_state('Open a trending post on the forum "space" and subscribe.')
    state["axtree"]["text"] = (
        "RootWebArea 'Postmill'\n"
        "  [54] searchbox 'Search query', clickable\n"
        "  [42] link 'Forums', clickable"
    )
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    guarded = Phase3WorldModelAgent._interaction_guard(
        state["goal"], candidates, ()
    )
    assert guarded is not None
    assert guarded[0] == 'fill("54", "space")'


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_world_model_protects_exact_task_query_fallback() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = _reddit_state("Upvote the newest post in deeplearning subreddit")
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    protected = Phase3WorldModelAgent._protected_observed_fallback(
        'fill("54", "deeplearning")',
        candidates,
    )
    assert protected is not None
    assert protected.action == 'fill("54", "deeplearning")'
    assert protected.source == "task_query"


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_world_model_does_not_protect_unrelated_structure_click() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = _reddit_state("Upvote the newest post in deeplearning subreddit")
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    protected = Phase3WorldModelAgent._protected_observed_fallback(
        'click("42", "left")',
        candidates,
    )
    assert protected is None


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_world_model_protects_exact_observed_upvote_control() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = {
        "goal": "Upvote the newest post in deeplearning subreddit",
        "url": "http://reddit.local/f/deeplearning/post",
        "axtree": {
            "text": (
                "RootWebArea 'Postmill'\n"
                "  [152] button 'Upvote', clickable\n"
                "  [134] link 'RandomForests92', clickable\n"
                "  [1317] link 'deeplearning', clickable"
            )
        },
    }
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    protected = Phase3WorldModelAgent._protected_observed_fallback(
        'click("152", "left")',
        candidates,
    )
    assert protected is not None
    assert protected.target_name == "Upvote"


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_interaction_guard_requires_exact_forum_name() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = _reddit_state('Open a trending post on the forum "space" and subscribe.')
    state["axtree"]["text"] = (
        "RootWebArea 'Search'\n"
        "  [124] link 'A long space news title', clickable\n"
        "  [136] link 'space', clickable"
    )
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    guarded = Phase3WorldModelAgent._interaction_guard(
        state["goal"], candidates, ('keyboard_press("Enter")',), state["url"]
    )
    assert guarded is not None
    assert guarded[0] == 'click("136", "left")'


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_interaction_guard_subscribes_then_opens_forum_thread() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    state = _reddit_state('Open a trending post on the forum "space" and subscribe.')
    state["url"] = "http://reddit.local/f/space"
    state["axtree"]["text"] = (
        "RootWebArea 'space'\n"
        "  [90] button 'Subscribe No subscribers', clickable\n"
        "  [143] link 'No comments', clickable"
    )
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    subscribe = Phase3WorldModelAgent._interaction_guard(
        state["goal"], candidates, (), state["url"]
    )
    assert subscribe is not None
    assert subscribe[0] == 'click("90", "left")'

    state["axtree"]["text"] = (
        "RootWebArea 'space'\n"
        "  [90] button 'Unsubscribe', clickable\n"
        "  [143] link 'No comments', clickable"
    )
    candidates = AXTreeCandidateGenerator(max_candidates=8).generate(state)
    thread = Phase3WorldModelAgent._interaction_guard(
        state["goal"], candidates, ('click("90", "left")',), state["url"]
    )
    assert thread is not None
    assert thread[0] == 'click("143", "left")'


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_world_model_terminates_when_reactive_observes_navigation_complete() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    # Exercise the early completion branch without constructing model weights.
    agent = object.__new__(Phase3WorldModelAgent)
    agent.encoder = type(
        "Encoder",
        (),
        {"encode": lambda self, state, history: type("Encoded", (), {"encoding_id": "test"})()},
    )()
    agent.reactive = ReactiveAgent()
    agent.navigation_guard = True
    decision = agent.decide(
        {
            "goal": "Check out the most recent open issues",
            "url": "http://gitlab.local/group/project/-/issues/?sort=created_asc&state=opened",
            "axtree": {"text": "RootWebArea 'Issues · GitLab'"},
        }
    )
    assert decision.action == 'send_msg_to_user("Done")'
    assert decision.mode == "observed_navigation_complete"
    assert decision.candidates == []


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
def test_world_model_uses_observed_gitlab_navigation_guard() -> None:
    from agent_world_model.phase3_agent import Phase3WorldModelAgent

    agent = object.__new__(Phase3WorldModelAgent)
    agent.encoder = type(
        "Encoder",
        (),
        {"encode": lambda self, state, history: type("Encoded", (), {"encoding_id": "test"})()},
    )()
    agent.reactive = ReactiveAgent()
    agent.navigation_guard = True
    decision = agent.decide(
        {
            "goal": "Check out my todos",
            "url": "http://gitlab.local/",
            "axtree": {
                "text": "RootWebArea 'GitLab'\n  [171] link 'To-Do List', clickable"
            },
        }
    )
    assert decision.action == 'click("171", "left")'
    assert decision.mode == "observed_navigation_guard"
    assert decision.candidates == []

    issue_sort = agent.decide(
        {
            "goal": "Check out the most recent open issues",
            "url": "http://gitlab.local/group/project/-/issues",
            "axtree": {
                "text": "RootWebArea 'Issues · GitLab'\n"
                "  [724] button 'Sort direction: Ascending', clickable"
            },
        }
    )
    assert issue_sort.action == 'click("724", "left")'
    assert issue_sort.mode == "observed_navigation_guard"
