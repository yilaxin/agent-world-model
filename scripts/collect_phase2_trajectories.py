#!/usr/bin/env python3
"""Collect a reproducible P0/P1 MiniWoB trajectory corpus.

The collector reuses one browser environment per task, records every executed
transition with the phase-one logger, and writes a resumable manifest.  A small,
deterministic safe-exploration fraction produces stalled/low-progress examples
instead of a success-only dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# NLTK's safe-path guard rejects an in-project virtualenv as the import CWD.
os.chdir("/tmp")

import gymnasium as gym  # noqa: E402

from agent_world_model import (  # noqa: E402
    ActionDecision,
    BaselineConfig,
    ReactiveAgent,
    run_baseline_episode,
)
from agent_world_model.baseline import register_browsergym_environment  # noqa: E402
from agent_world_model.reactive_agent import parse_elements  # noqa: E402


class SafeExplorationAgent:
    """Inject deterministic scroll alternatives without invalid action syntax."""

    policy_name = "reactive_rules_v1_safe_exploration"

    def __init__(self, *, seed: int, rate: float) -> None:
        self.seed = seed
        self.rate = rate
        self.base = ReactiveAgent()

    def decide(
        self,
        state,
        recent_actions: Sequence[str] = (),
        *,
        direct_answer: str | None = None,
    ) -> ActionDecision:
        digest = hashlib.sha256(
            f"{self.seed}:{getattr(state, 'state_id', '')}:{len(recent_actions)}".encode()
        ).digest()
        explore = int.from_bytes(digest[:8], "big") / (2**64 - 1) < self.rate
        if explore:
            direction = -600 if digest[8] & 1 else 600
            return ActionDecision(
                action=f"scroll(0, {direction})",
                action_type="scroll",
                rationale="Deterministic safe exploration for negative/stalled labels.",
                confidence=0.30,
            )
        return self.base.decide(
            state, recent_actions, direct_answer=direct_answer
        )


class TerminalWrongTargetAgent:
    """Build H=3 trajectories ending in an observed wrong-target failure."""

    policy_name = "terminal_wrong_target_probe_v1"

    def __init__(self, *, seed: int) -> None:
        self.seed = seed
        self.base = ReactiveAgent()

    def decide(
        self,
        state,
        recent_actions: Sequence[str] = (),
        *,
        direct_answer: str | None = None,
    ) -> ActionDecision:
        if len(recent_actions) < 2:
            direction = -600 if (self.seed + len(recent_actions)) % 2 else 600
            return ActionDecision(
                action=f"scroll(0, {direction})",
                action_type="scroll",
                rationale="Preserve a real pre-failure context for H=3 evaluation.",
                confidence=1.0,
            )
        factual = self.base.decide(
            state,
            recent_actions,
            direct_answer=direct_answer,
        )
        alternatives = sorted(
            (
                item
                for item in parse_elements(state.axtree.text)
                if item.role in {"button", "link", "option", "tab"}
                and item.bid != factual.target_bid
            ),
            key=lambda item: (item.role, item.name, item.bid),
        )
        if alternatives:
            target = alternatives[self.seed % len(alternatives)]
            return ActionDecision(
                action=f'click("{target.bid}", "left")',
                action_type="click",
                rationale="Execute a visible wrong target and observe terminal failure.",
                target_bid=target.bid,
                target_name=target.name,
                confidence=1.0,
            )
        return ActionDecision(
            action='click("phase2-terminal-wrong-target", "left")',
            action_type="click",
            rationale="Execute an absent wrong target when no alternative is visible.",
            target_bid="phase2-terminal-wrong-target",
            target_name="<deliberately absent>",
            confidence=1.0,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase2_collection.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories_phase2",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase2_collection_latest.json",
    )
    parser.add_argument(
        "--limit-episodes",
        type=int,
        help="Bounded smoke run; formal collection should omit this option.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = (
        args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    )
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else PROJECT_ROOT / args.output_dir
    )
    report_path = (
        args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    )
    if not os.environ.get("MINIWOB_URL"):
        raise RuntimeError("MINIWOB_URL is not set; source the phase-one .env first")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in config["seeds"]]
    tasks = [str(task) for task in config["tasks"]]
    agent_mode = str(config.get("agent_mode", "safe_exploration"))
    if agent_mode not in {"safe_exploration", "terminal_wrong_target"}:
        raise ValueError(f"unsupported agent_mode: {agent_mode}")
    planned = [(task, seed) for task in tasks for seed in seeds]
    if args.limit_episodes is not None:
        planned = planned[: args.limit_episodes]

    results = []
    failures = []
    completed = 0
    for task in tasks:
        task_runs = [(item, seed) for item, seed in planned if item == task]
        if not task_runs:
            continue
        register_browsergym_environment(task)
        env = gym.make(task, headless=bool(config["headless"]))
        try:
            for _, seed in task_runs:
                try:
                    result = run_baseline_episode(
                        BaselineConfig(
                            env_id=task,
                            seed=seed,
                            max_steps=int(config["max_steps"]),
                            headless=bool(config["headless"]),
                        ),
                        output_dir=output_dir,
                        env=env,
                        agent=(
                            TerminalWrongTargetAgent(seed=seed)
                            if agent_mode == "terminal_wrong_target"
                            else SafeExplorationAgent(
                                seed=seed,
                                rate=float(config["safe_exploration_rate"]),
                            )
                        ),
                    )
                    results.append(result.to_dict())
                except Exception as error:
                    failures.append(
                        {"env_id": task, "seed": seed, "error": repr(error)}
                    )
                completed += 1
                if completed % 25 == 0 or completed == len(planned):
                    print(f"completed={completed}/{len(planned)} failures={len(failures)}")
        finally:
            env.close()

    transition_count = sum(int(item["steps"]) for item in results)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "planned_episodes": len(planned),
        "completed_episodes": len(results),
        "failed_episodes": len(failures),
        "transition_count": transition_count,
        "successful_episodes": sum(bool(item["success"]) for item in results),
        "p0_500_transitions": transition_count >= 500,
        "p1_3000_transitions": transition_count >= 3000,
        "results": results,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in report.items() if key not in {
        "results", "failures", "config"
    }}, ensure_ascii=False, indent=2))
    return 0 if transition_count >= int(config["minimum_transitions"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
