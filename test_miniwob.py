from __future__ import annotations

import os
import re

import browsergym.miniwob
import gymnasium as gym
from browsergym.utils.obs import flatten_axtree_to_str


def main() -> None:
    miniwob_url = os.environ.get("MINIWOB_URL")

    if not miniwob_url:
        raise RuntimeError(
            "没有检测到 MINIWOB_URL，请先执行：source .env"
        )

    env_id = "browsergym/miniwob.click-test"

    print("Environment:", env_id)
    print("MiniWoB URL:", miniwob_url)

    env = gym.make(
        env_id,
        headless=True,
    )

    try:
        obs, info = env.reset(seed=0)

        print("\nReset succeeded.")
        print("Observation type:", type(obs))
        print("Observation keys:")

        for key in obs.keys():
            print(" -", key)

        print("\nGoal:")
        print(obs.get("goal"))

        print("\nCurrent URL:")
        print(obs.get("url"))

        screenshot = obs.get("screenshot")
        if screenshot is not None:
            print("\nScreenshot shape:", screenshot.shape)

        axtree_text = flatten_axtree_to_str(
            obs["axtree_object"],
            extra_properties=obs["extra_element_properties"],
            with_clickable=True,
            skip_generic=True,
            filter_visible_only=True,
        )

        print("\nAccessibility tree:")
        print(axtree_text)

        button_match = re.search(
            r"\[([^\]]+)\]\s+button\b",
            axtree_text,
            re.IGNORECASE,
        )

        if button_match is None:
            raise RuntimeError("没有在可访问性树中找到按钮")

        button_bid = button_match.group(1)
        action = f'click("{button_bid}", "left")'

        print("\nExecuting action:", action)

        next_obs, reward, terminated, truncated, step_info = env.step(
            action
        )

        print("\nClick step succeeded.")
        print("Reward:", reward)
        print("Terminated:", terminated)
        print("Truncated:", truncated)
        print("Last action:", next_obs.get("last_action"))
        print(
            "Last action error:",
            next_obs.get("last_action_error"),
        )

    finally:
        env.close()
        print("\nEnvironment closed.")


if __name__ == "__main__":
    main()