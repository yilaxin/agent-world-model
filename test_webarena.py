from __future__ import annotations

import json
import os
from typing import Any

# NLTK 3.10's import guard treats an in-project virtualenv as untrusted CWD
# content. Move away from the project before importing BrowserGym/NLTK.
os.chdir("/tmp")

import browsergym.webarena  # noqa: F401 - registers WebArena tasks
import gymnasium as gym


ENV_ID = "browsergym/webarena.27"
EXPECTED_ANSWER = "0"


def printable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def main() -> None:
    print(f"Environment: {ENV_ID}")

    env = gym.make(ENV_ID, headless=True)
    try:
        observation, reset_info = env.reset(seed=0)
        print("Reset succeeded.")
        print("Goal:", printable(observation.get("goal")))
        print("URL:", printable(observation.get("url")))
        print("Reset info:", json.dumps(reset_info, ensure_ascii=False, default=str))

        action = f'send_msg_to_user("{EXPECTED_ANSWER}")'
        print("Action:", action)
        _, reward, terminated, truncated, step_info = env.step(action)

        print("Reward:", float(reward))
        print("Terminated:", bool(terminated))
        print("Truncated:", bool(truncated))
        print("Evaluator info:", json.dumps(step_info, ensure_ascii=False, default=str))

        if float(reward) != 1.0 or not terminated or truncated:
            raise RuntimeError("WebArena evaluator did not report a successful task.")

        print("WebArena fixed-task evaluation passed.")
    finally:
        env.close()
        print("Environment closed.")


if __name__ == "__main__":
    main()
