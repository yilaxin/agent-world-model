"""Reusable phase-one reactive baseline loop."""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import gymnasium as gym

from .encoder import StateEncoderV1
from .reactive_agent import ReactiveAgent
from .state import StateExtractor
from .trajectory import TrajectoryLogger


@dataclass(frozen=True)
class BaselineConfig:
    env_id: str
    seed: int = 0
    max_steps: int = 10
    headless: bool = True
    direct_answer: str | None = None

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")


@dataclass(frozen=True)
class EpisodeResult:
    env_id: str
    seed: int
    success: bool
    terminated: bool
    truncated: bool
    steps: int
    total_reward: float
    last_action_error: str
    trajectory_path: str
    final_state_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def register_browsergym_environment(env_id: str) -> None:
    if "/miniwob." in env_id:
        importlib.import_module("browsergym.miniwob")
    elif "/webarena." in env_id:
        importlib.import_module("browsergym.webarena")
    else:
        importlib.import_module("browsergym.core")


def run_baseline_episode(
    config: BaselineConfig,
    *,
    output_dir: str | Path,
    env: Any | None = None,
    extractor: StateExtractor | None = None,
    encoder: StateEncoderV1 | None = None,
    agent: ReactiveAgent | None = None,
) -> EpisodeResult:
    """Run reset → observe → decide → act → evaluate with complete logging."""

    register_browsergym_environment(config.env_id)
    owns_env = env is None
    if env is None:
        env_kwargs: dict[str, Any] = {"headless": config.headless}
        if "/webarena." in config.env_id:
            # Match WebArena's documented action vocabulary. BrowserGym's
            # generic default instead exposes the element-scoped ``press``
            # action and omits WebArena's page-level ``keyboard_press``.
            from browsergym.core.action.highlevel import HighLevelActionSet

            env_kwargs["action_mapping"] = HighLevelActionSet(
                subsets="webarena"
            ).to_python_code
        env = gym.make(config.env_id, **env_kwargs)

    extractor = extractor or StateExtractor()
    encoder = encoder or StateEncoderV1()
    agent = agent or ReactiveAgent()
    recent_actions: list[str] = []
    total_reward = 0.0
    terminated = False
    truncated = False
    last_action_error = ""
    final_state_id = ""

    try:
        observation, _ = env.reset(seed=config.seed)
        state = extractor.extract(observation)
        final_state_id = state.state_id

        with TrajectoryLogger.create(
            output_dir,
            env_id=config.env_id,
            seed=config.seed,
        ) as logger:
            for _ in range(config.max_steps):
                encoded_state = encoder.encode(state, recent_actions)
                decision = agent.decide(
                    state,
                    recent_actions,
                    direct_answer=config.direct_answer,
                )
                next_observation, reward, terminated, truncated, step_info = env.step(
                    decision.action
                )
                next_state = extractor.extract(next_observation)
                next_actions = [*recent_actions, decision.action]
                encoded_next_state = encoder.encode(next_state, next_actions)

                logger.record_transition(
                    state=state,
                    action=decision.action,
                    next_state=next_state,
                    reward=reward,
                    terminated=terminated,
                    truncated=truncated,
                    info=step_info,
                    encoded_state=encoded_state.to_compact_dict(),
                    encoded_next_state=encoded_next_state.to_compact_dict(),
                    decision=decision.to_dict(),
                )

                total_reward += float(reward)
                recent_actions = next_actions[-encoder.config.recent_action_count :]
                state = next_state
                final_state_id = state.state_id
                last_action_error = state.last_action_error
                if terminated or truncated:
                    break

            trajectory_path = str(logger.path)
            steps = logger.step_count
    finally:
        if owns_env:
            env.close()

    return EpisodeResult(
        env_id=config.env_id,
        seed=config.seed,
        success=bool(total_reward > 0.0 and terminated and not truncated),
        terminated=bool(terminated),
        truncated=bool(truncated),
        steps=steps,
        total_reward=total_reward,
        last_action_error=last_action_error,
        trajectory_path=trajectory_path,
        final_state_id=final_state_id,
    )
