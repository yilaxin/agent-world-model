#!/usr/bin/env python3
"""Execute input, scroll, click and back through BrowserGym and log each step."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir("/tmp")

import browsergym.core  # noqa: E402,F401 - registers the open-ended task
import gymnasium as gym  # noqa: E402

from agent_world_model import (  # noqa: E402
    ReactiveAgent,
    StateEncoderV1,
    StateExtractor,
    TrajectoryLogger,
)


def main() -> int:
    first_page = PROJECT_ROOT / "tests" / "fixtures" / "phase1_interactions.html"
    second_page = PROJECT_ROOT / "tests" / "fixtures" / "phase1_second.html"
    env_id = "browsergym/openended"
    env = gym.make(
        env_id,
        task_kwargs={
            "start_url": first_page.resolve().as_uri(),
            "goal": "Phase-one interaction API smoke test.",
        },
        headless=True,
        pre_observation_delay=0.05,
    )
    extractor = StateExtractor()
    encoder = StateEncoderV1()
    agent = ReactiveAgent()
    action_history: list[str] = []
    action_types: list[str] = []

    instructions = [
        ('Enter "phase-one-ok" into the Phase one text field.', "input"),
        ("Scroll down to the bottom of the page.", "scroll"),
        ("Click the Open second page link.", "click"),
        ("Go back to the previous page.", "back"),
    ]

    try:
        observation, _ = env.reset(seed=0)
        state = extractor.extract(observation)
        with TrajectoryLogger.create(
            PROJECT_ROOT / "data" / "trajectories",
            env_id=env_id,
            seed=0,
        ) as logger:
            for instruction, expected_type in instructions:
                state_for_agent = replace(state, goal=instruction)
                encoded_state = encoder.encode(state_for_agent, action_history)
                decision = agent.decide(state_for_agent, action_history)
                if decision.action_type != expected_type:
                    raise AssertionError(
                        f"Expected {expected_type}, got {decision.action_type}: "
                        f"{decision.action}"
                    )

                next_observation, reward, terminated, truncated, info = env.step(
                    decision.action
                )
                next_state = extractor.extract(next_observation)
                if next_state.last_action_error:
                    raise RuntimeError(
                        f"{expected_type} failed: {next_state.last_action_error}"
                    )
                if expected_type == "input" and "phase-one-ok" not in (
                    next_state.axtree.text + next_state.dom.text
                ):
                    raise AssertionError("Input value was not reflected in the page state.")
                if expected_type == "click" and Path(next_state.url).name != second_page.name:
                    raise AssertionError(
                        f"Click did not reach {second_page.name}: {next_state.url}"
                    )
                next_history = [*action_history, decision.action]
                encoded_next = encoder.encode(next_state, next_history)
                logger.record_transition(
                    state=state_for_agent,
                    action=decision.action,
                    next_state=next_state,
                    reward=reward,
                    terminated=terminated,
                    truncated=truncated,
                    info=info,
                    encoded_state=encoded_state.to_compact_dict(),
                    encoded_next_state=encoded_next.to_compact_dict(),
                    decision=decision.to_dict(),
                )
                action_types.append(decision.action_type)
                action_history = next_history[-encoder.config.recent_action_count :]
                state = next_state

            if Path(state.url).name != first_page.name:
                raise AssertionError(f"Back action returned to unexpected URL: {state.url}")
            report = {
                "success": action_types == ["input", "scroll", "click", "back"],
                "action_types": action_types,
                "trajectory_path": str(logger.path),
                "returned_to_start": Path(state.url).name == first_page.name,
                "visited_page": second_page.name,
            }
    finally:
        env.close()

    report_path = PROJECT_ROOT / "data" / "reports" / "phase1_actions_latest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] and report["returned_to_start"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
