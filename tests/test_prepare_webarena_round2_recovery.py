from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "prepare_webarena_round2_recovery.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("round2_recovery", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recovery_module_loads() -> None:
    module = _module()
    assert callable(module.main)
