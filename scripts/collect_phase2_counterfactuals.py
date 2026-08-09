#!/usr/bin/env python3
"""Collect paired factual/counterfactual BrowserGym transitions by execution.

Each pair resets the same task with the same seed.  The factual arm
executes the deterministic reactive policy; the counterfactual arm executes a
controlled alternative.  Both outcomes therefore come from the environment,
not from model-generated labels.  A shared episode id keeps each pair in one
dataset split and prevents counterfactual leakage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir("/tmp")

import gymnasium as gym  # noqa: E402

from agent_world_model.baseline import register_browsergym_environment  # noqa: E402
from agent_world_model.counterfactual import observed_utility  # noqa: E402
from agent_world_model.encoder import StateEncoderV1  # noqa: E402
from agent_world_model.phase2_schema import canonicalize_transition  # noqa: E402
from agent_world_model.reactive_agent import (  # noqa: E402
    ActionDecision,
    ReactiveAgent,
    parse_elements,
)
from agent_world_model.state import StateExtractor  # noqa: E402
from agent_world_model.trajectory import TrajectoryLogger, load_trajectory  # noqa: E402


DEFAULT_TASKS = [
    "browsergym/miniwob.click-button",
    "browsergym/miniwob.click-link",
    "browsergym/miniwob.click-option",
    "browsergym/miniwob.click-test-2",
    "browsergym/miniwob.click-dialog",
    "browsergym/miniwob.click-dialog-2",
    "browsergym/miniwob.click-tab-2-easy",
    "browsergym/miniwob.click-widget",
    "browsergym/miniwob.click-checkboxes",
    "browsergym/miniwob.sign-agreement",
]

DEFAULT_STRATEGIES = (
    "hard_wrong_target",
    "wrong_action_type",
    "missing_target",
)


def _counterfactual_decision(
    state: Any,
    factual: ActionDecision,
    *,
    strategy: str,
    seed: int,
) -> ActionDecision:
    elements = parse_elements(state.axtree.text)
    clickable_roles = {"button", "link", "checkbox", "radio", "option", "menuitem", "tab"}
    alternatives = [
        item
        for item in elements
        if item.role in clickable_roles and item.bid != factual.target_bid
    ]
    alternatives = sorted(alternatives, key=lambda item: (item.role, item.name, item.bid))
    if strategy == "hard_wrong_target" and alternatives:
        digest = hashlib.sha256(f"{seed}:{factual.action}:{strategy}".encode()).digest()
        target = alternatives[int.from_bytes(digest[:4], "big") % len(alternatives)]
        return ActionDecision(
            action=f'click({json.dumps(target.bid)}, "left")',
            action_type="click",
            rationale="Executed seeded visible wrong-target counterfactual.",
            target_bid=target.bid,
            target_name=target.name,
            confidence=1.0,
        )
    if strategy == "wrong_action_type" and factual.target_bid:
        if factual.action_type in {"fill", "type"}:
            action = f'click({json.dumps(factual.target_bid)}, "left")'
            action_type = "click"
        else:
            action = f'fill({json.dumps(factual.target_bid)}, "counterfactual_wrong_value")'
            action_type = "fill"
        return ActionDecision(
            action=action,
            action_type=action_type,
            rationale="Executed wrong-action-type counterfactual on the factual target.",
            target_bid=factual.target_bid,
            target_name=factual.target_name,
            confidence=1.0,
        )
    if strategy == "hard_wrong_target" and alternatives:
        target = alternatives[0]
        return ActionDecision(
            action=f'click({json.dumps(target.bid)}, "left")',
            action_type="click",
            rationale="Executed fallback visible wrong-target counterfactual.",
            target_bid=target.bid,
            target_name=target.name,
            confidence=1.0,
        )
    return ActionDecision(
        action='click("phase2-counterfactual-missing-target", "left")',
        action_type="click",
        rationale="Executed missing-target counterfactual when no visible alternative existed.",
        target_bid="phase2-counterfactual-missing-target",
        target_name="<deliberately absent>",
        confidence=1.0,
    )


def _run_arm(
    env: Any,
    *,
    task: str,
    seed: int,
    pair_id: str,
    group_id: str,
    role: str,
    intervention_type: str,
    output_dir: Path,
    extractor: StateExtractor,
    encoder: StateEncoderV1,
    agent: ReactiveAgent,
) -> dict[str, Any]:
    observation, _ = env.reset(seed=seed)
    state = extractor.extract(observation)
    factual = agent.decide(state, ())
    decision = (
        factual
        if role == "factual"
        else _counterfactual_decision(
            state,
            factual,
            strategy=intervention_type,
            seed=seed,
        )
    )
    next_observation, reward, terminated, truncated, info = env.step(decision.action)
    next_state = extractor.extract(next_observation)
    encoded_state = encoder.encode(state, ())
    encoded_next_state = encoder.encode(next_state, (decision.action,))
    intervention = "recorded_policy" if role == "factual" else decision.rationale
    with TrajectoryLogger.create(
        output_dir,
        env_id=task,
        seed=seed,
        episode_id=pair_id,
    ) as logger:
        logger.record_transition(
            state=state,
            action=decision.action,
            next_state=next_state,
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            info=info,
            encoded_state=encoded_state.to_compact_dict(),
            encoded_next_state=encoded_next_state.to_compact_dict(),
            decision=decision.to_dict(),
            metadata={
                "counterfactual_pair_id": pair_id,
                "counterfactual_group_id": group_id,
                "counterfactual_role": role,
                "intervention": intervention,
                "intervention_type": intervention_type,
                "observed_in_environment": True,
                "initial_state_id": state.state_id,
            },
        )
        path = logger.path
    record = load_trajectory(path)[0]
    example = canonicalize_transition(record)
    return {
        "path": str(path),
        "pair_id": pair_id,
        "role": role,
        "initial_state_id": state.state_id,
        "action": decision.action,
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "invalid_action": bool(example.task_signals["invalid_action"]),
        "severe_failure": bool(example.risks["severe_failure"]),
        "success": bool(example.risks["success"]),
        "task_signals": dict(example.task_signals),
        "risks": dict(example.risks),
        "utility": observed_utility(example),
        "intervention_type": intervention_type,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "trajectories_phase2_counterfactual")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "data" / "reports" / "phase2_counterfactual_collection_latest.json")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--seed-offset", type=int, default=1000)
    parser.add_argument("--limit-pairs", type=int)
    parser.add_argument(
        "--tasks-config",
        type=Path,
        help="Optional JSON config containing a tasks list.",
    )
    parser.add_argument(
        "--strategies",
        default=",".join(DEFAULT_STRATEGIES),
        help="Comma-separated intervention strategies.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    tasks = list(DEFAULT_TASKS)
    if args.tasks_config:
        tasks_path = (
            args.tasks_config
            if args.tasks_config.is_absolute()
            else PROJECT_ROOT / args.tasks_config
        )
        tasks_config = json.loads(tasks_path.read_text(encoding="utf-8"))
        tasks = [str(task) for task in tasks_config.get("tasks", [])]
        if not tasks:
            raise ValueError("tasks-config must contain a non-empty tasks list")
    if any("/miniwob." in task for task in tasks) and not os.environ.get("MINIWOB_URL"):
        raise RuntimeError("MINIWOB_URL is not set; source the phase-one .env first")
    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    unsupported = sorted(set(strategies) - set(DEFAULT_STRATEGIES))
    if unsupported:
        raise ValueError(f"unsupported counterfactual strategies: {unsupported}")
    planned = [
        (task, args.seed_offset + seed, strategy)
        for task in tasks
        for seed in range(args.seeds)
        for strategy in strategies
    ]
    if args.limit_pairs is not None:
        planned = planned[: args.limit_pairs]
    extractor, encoder, agent = StateExtractor(), StateEncoderV1(), ReactiveAgent()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for task in tasks:
        task_runs = [
            (seed, strategy)
            for current_task, seed, strategy in planned
            if current_task == task
        ]
        if not task_runs:
            continue
        register_browsergym_environment(task)
        env = gym.make(task, headless=True)
        try:
            for seed, strategy in task_runs:
                group_id = f"cfgroup-{task.rsplit('.', 1)[-1]}-seed{seed}"
                pair_id = f"cf-{task.rsplit('.', 1)[-1]}-seed{seed}-{strategy}"
                try:
                    factual = _run_arm(
                        env,
                        task=task,
                        seed=seed,
                        pair_id=pair_id,
                        group_id=group_id,
                        role="factual",
                        intervention_type=strategy,
                        output_dir=output_dir,
                        extractor=extractor,
                        encoder=encoder,
                        agent=agent,
                    )
                    counterfactual = _run_arm(
                        env,
                        task=task,
                        seed=seed,
                        pair_id=pair_id,
                        group_id=group_id,
                        role="counterfactual",
                        intervention_type=strategy,
                        output_dir=output_dir,
                        extractor=extractor,
                        encoder=encoder,
                        agent=agent,
                    )
                    rows.extend([factual, counterfactual])
                except Exception as error:
                    failures.append(
                        {"task": task, "seed": seed, "strategy": strategy, "error": repr(error)}
                    )
        finally:
            env.close()
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_pair.setdefault(row["pair_id"], []).append(row)
    valid_pairs = [
        pair
        for pair in by_pair.values()
        if len(pair) == 2
        and len({item["role"] for item in pair}) == 2
        and len({item["initial_state_id"] for item in pair}) == 1
    ]
    informative_pairs = [
        pair
        for pair in valid_pairs
        if abs(float(pair[0]["utility"]) - float(pair[1]["utility"])) >= 0.05
    ]
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "planned_pairs": len(planned),
        "valid_pairs": len(valid_pairs),
        "informative_pairs": len(informative_pairs),
        "informative_pair_rate": len(informative_pairs) / max(1, len(valid_pairs)),
        "failed_pairs": len(failures),
        "transition_count": len(rows),
        "counterfactual_invalid_action_positives": sum(item["role"] == "counterfactual" and item["invalid_action"] for item in rows),
        "counterfactual_severe_failure_positives": sum(item["role"] == "counterfactual" and item["severe_failure"] for item in rows),
        "counterfactual_successes": sum(item["role"] == "counterfactual" and item["success"] for item in rows),
        "pair_state_match_rate": len(valid_pairs) / max(1, len(by_pair)),
        "task_count": len(tasks),
        "strategies": strategies,
        "strategy_counts": {
            strategy: sum(
                item["role"] == "counterfactual"
                and item["intervention_type"] == strategy
                for item in rows
            )
            for strategy in strategies
        },
        "observed_outcomes_only": True,
        "rows": rows,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"rows", "failures"}}, ensure_ascii=False, indent=2))
    return 0 if valid_pairs and not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
