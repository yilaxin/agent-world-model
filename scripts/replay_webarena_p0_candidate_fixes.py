#!/usr/bin/env python3
"""Replay frozen P0 observations through the repaired candidate generator.

This is a diagnostic counterfactual over recorded observations, not an online
WebArena success-rate estimate.  It never advances or mutates an environment.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_world_model.phase3_candidates import AXTreeCandidateGenerator  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data/trajectories_webarena_p0_evidence/manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/reports/webarena_p0_candidate_fix_replay.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    episodes = []
    totals = Counter()
    for item in manifest["episodes"]:
        path = ROOT / item["path"]
        old_rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        history: list[str] = []
        replay_rows = []
        for row in old_rows:
            old_action = str(row.get("action") or "")
            old_target = ""
            decision = row.get("decision") or {}
            for candidate in decision.get("candidates") or []:
                if candidate.get("action") == old_action:
                    old_target = str(candidate.get("target_name") or "")
                    break
            generator = AXTreeCandidateGenerator(
                max_candidates=8,
                navigation_guard=str(item["cell"]).endswith("guard_on"),
            )
            candidates = generator.generate(row["state"], history)
            new_actions = [candidate.action for candidate in candidates]
            new_names = [candidate.target_name for candidate in candidates]
            logout_old = "sign out" in old_target.casefold() or "logout" in old_action.casefold()
            logout_new = any("sign out" in name.casefold() for name in new_names)
            repeated_old = old_action in history[-6:]
            old_retained = old_action in new_actions
            totals["steps"] += 1
            totals["old_logout_steps"] += int(logout_old)
            totals["new_logout_candidates"] += int(logout_new)
            totals["old_repeated_steps"] += int(repeated_old)
            totals["repeated_old_action_suppressed"] += int(repeated_old and not old_retained)
            totals["old_action_removed"] += int(not old_retained)
            replay_rows.append(
                {
                    "step_index": row.get("step_index"),
                    "old_action": old_action,
                    "old_target_name": old_target,
                    "old_action_repeated": repeated_old,
                    "old_action_retained": old_retained,
                    "new_top_action": new_actions[0] if new_actions else "",
                    "new_top_target_name": new_names[0] if new_names else "",
                    "new_candidate_count": len(candidates),
                    "unrequested_logout_present": logout_new,
                }
            )
            history.append(old_action)
        episodes.append(
            {
                "site": item["site"],
                "cell": item["cell"],
                "task_id": item["task_id"],
                "trajectory_path": item["path"],
                "rows": replay_rows,
            }
        )
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "offline_candidate_replay_on_recorded_observations",
        "online_success_rate_estimate": False,
        "limitations": [
            "后续页面仍来自旧策略轨迹，因此不能串联成新策略 episode。",
            "该回放只验证候选集合的局部不变量，不验证任务成功。",
        ],
        "summary": dict(totals),
        "episodes": episodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
