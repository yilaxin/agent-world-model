from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "prepare_webarena_p0_round2.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("round2_prepare", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_incomplete_analysis_cannot_freeze_holdout(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "partial.json"
    report.write_text(
        json.dumps(
            {
                "complete": False,
                "metrics": {"world-model": {"episodes": 15, "successes": 1}},
            }
        ),
        encoding="utf-8",
    )
    try:
        module.dev_successes(report)
    except ValueError as error:
        assert "incomplete" in str(error)
    else:
        raise AssertionError("incomplete development analysis passed the freeze gate")


def test_complete_30_episode_w4_analysis_passes_gate(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "complete.json"
    report.write_text(
        json.dumps(
            {
                "complete": True,
                "metrics": {"world-model": {"episodes": 30, "successes": 2}},
            }
        ),
        encoding="utf-8",
    )
    assert module.dev_successes(report) == (2, 30)
