#!/usr/bin/env python3
"""Print the unpruned AXTree for one authenticated WebArena task page."""

from __future__ import annotations

import argparse

import gymnasium as gym


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--action",
        action="append",
        default=[],
        help="Optional high-level action to execute after navigation; repeatable.",
    )
    args = parser.parse_args()

    import browsergym.webarena  # noqa: F401
    from browsergym.core.action.highlevel import HighLevelActionSet
    from browsergym.utils.obs import flatten_axtree_to_str

    env = gym.make(
        f"browsergym/webarena.{args.task_id}",
        headless=True,
        action_mapping=HighLevelActionSet(subsets="webarena").to_python_code,
    )
    try:
        env.reset(seed=0)
        observation, *_ = env.step(f'goto("{args.url}")')
        print(f"URL_AFTER_NAVIGATION={observation['url']}")
        for action in args.action:
            observation, reward, terminated, truncated, _ = env.step(action)
            print(
                f"URL_AFTER_ACTION={observation['url']} ACTION={action} "
                f"REWARD={reward} TERMINATED={terminated} TRUNCATED={truncated}"
            )
            if terminated or truncated:
                break
        print(
            flatten_axtree_to_str(
                observation["axtree_object"],
                extra_properties=observation["extra_element_properties"],
                with_clickable=True,
                skip_generic=True,
                filter_visible_only=True,
            )
        )
    finally:
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
