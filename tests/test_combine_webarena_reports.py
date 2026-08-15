from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "combine_webarena_formal_reports.py"


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "benchmark": "test benchmark",
                "task_ids": [7],
                "task_sites": {"7": "reddit"},
                "seeds": [0],
                "reactive_step_budget": 12,
                "world_model_step_budget": 12,
                "episode_max_attempts": 2,
                "evaluation_status": "post_fix_regression",
                "task_feedback_used": True,
                "shared_navigation_guard": True,
                "notes": ["test caveat"],
                "scope_limit": "test only",
            }
        ),
        encoding="utf-8",
    )
    return path


def _report(tmp_path: Path, mode: str, *, injected: bool = False) -> Path:
    trajectory = tmp_path / f"{mode}.jsonl"
    trajectory.write_text("{}\n", encoding="utf-8")
    row = {
        "mode": mode,
        "task_id": 7,
        "seed": 0,
        "site": "reddit",
        "success": True,
        "steps": 2,
        "attempted_actions": 1,
        "action_execution_successes": 1,
        "elapsed_seconds": 1.0,
        "episode_attempts": 1,
        "uses_expected_answer": injected,
        "trajectory_path": str(trajectory),
        "trajectory_sha256": hashlib.sha256(trajectory.read_bytes()).hexdigest(),
    }
    path = tmp_path / f"{mode}.json"
    path.write_text(
        json.dumps(
            {
                "benchmark": "test benchmark",
                "budgets": {"reactive_steps": 12, "world_model_steps": 12},
                "agent_success_rate_excludes_answer_injection": True,
                "results": {mode: [row]},
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def _run(tmp_path: Path, *, injected: bool = False) -> subprocess.CompletedProcess[str]:
    output = tmp_path / "combined.json"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(_manifest(tmp_path)),
            "--report",
            str(_report(tmp_path, "reactive", injected=injected)),
            "--report",
            str(_report(tmp_path, "world-model")),
            "--output",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_combiner_marks_post_fix_shared_guard_result(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "combined.json").read_text(encoding="utf-8"))
    assert payload["evaluation_status"] == "post_fix_regression"
    assert payload["task_feedback_used"] is True
    assert payload["shared_navigation_guard"] is True
    assert payload["world_model_attribution_claim"] is False
    assert payload["paired_online_comparison"]["paired_task_count"] == 1


def test_combiner_rejects_answer_injection(tmp_path: Path) -> None:
    result = _run(tmp_path, injected=True)
    assert result.returncode != 0
    assert "answer injection is forbidden" in result.stderr
