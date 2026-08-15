from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "analyze_webarena_round2_dev.py"
)


def test_round2_dev_analysis_extracts_both_report_shapes() -> None:
    spec = importlib.util.spec_from_file_location("round2_analysis", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    standard = {"results": {"world-model": [{"mode": "world-model", "task_id": 1}]}}
    recovery = {"results": [{"mode": "reactive", "task_id": 2}]}
    assert module.result_rows(standard, "world-model")[0]["task_id"] == 1
    assert module.result_rows(recovery, "reactive")[0]["task_id"] == 2
