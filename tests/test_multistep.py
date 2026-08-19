from __future__ import annotations

import unittest

from agent_world_model.multistep import build_horizon_windows, multistep_coverage_summary


def _record(episode: str, step: int, *, terminal: bool = False, severe: bool = False) -> dict:
    return {
        "episode_id": episode,
        "task_id": "task-a",
        "step_index": step,
        "task_signals": {"terminal": float(terminal), "invalid_action": 0.0},
        "risks": {"success": 0.0, "severe_failure": float(severe)},
    }


class MultiStepTests(unittest.TestCase):
    def test_windows_are_contiguous_and_do_not_cross_terminal(self) -> None:
        records = [
            _record("ep-a", 0),
            _record("ep-a", 1, terminal=True, severe=True),
            _record("ep-a", 2),
            _record("ep-b", 0),
            _record("ep-b", 2),
        ]
        windows = build_horizon_windows(records)
        self.assertEqual(len(windows[1]), 5)
        self.assertEqual(len(windows[2]), 1)
        self.assertEqual([row["step_index"] for row in windows[2][0]], [0, 1])
        self.assertEqual(len(windows[3]), 0)

    def test_coverage_counts_terminal_and_severe_endings(self) -> None:
        records = [_record("ep-a", 0), _record("ep-a", 1, terminal=True, severe=True)]
        summary = multistep_coverage_summary(build_horizon_windows(records))
        self.assertEqual(summary["by_horizon"]["2"]["terminal_ending_count"], 1)
        self.assertEqual(summary["long_horizon_severe_failure_count"], 1)

    def test_invalid_horizon_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_horizon_windows([], max_horizon=4)


if __name__ == "__main__":
    unittest.main()
