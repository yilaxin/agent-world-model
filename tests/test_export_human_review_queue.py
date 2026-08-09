from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_human_review_queue.py"
SPEC = importlib.util.spec_from_file_location("export_human_review_queue", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_files_ignores_missing_optional_input(tmp_path: Path) -> None:
    existing = tmp_path / "trajectories"
    existing.mkdir()
    trajectory = existing / "episode.jsonl"
    trajectory.write_text("{}\n", encoding="utf-8")

    discovered = MODULE._files([existing, tmp_path / "missing-webarena"])

    assert discovered == [trajectory]


def test_files_ignores_non_jsonl_files_inside_directories(tmp_path: Path) -> None:
    source = tmp_path / "trajectories"
    source.mkdir()
    trajectory = source / "episode.jsonl"
    trajectory.write_text("{}\n", encoding="utf-8")
    (source / "notes.txt").write_text("not a trajectory", encoding="utf-8")

    assert MODULE._files([source]) == [trajectory]
