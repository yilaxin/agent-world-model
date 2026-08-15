"""Deterministic content fingerprint for a frozen WebArena Agent release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


RELEASE_SOURCE_PATHS = (
    "agent_world_model/__init__.py",
    "agent_world_model/baseline.py",
    "agent_world_model/encoder.py",
    "agent_world_model/experiment_stats.py",
    "agent_world_model/phase2_dataset.py",
    "agent_world_model/phase2_ensemble.py",
    "agent_world_model/phase2_losses.py",
    "agent_world_model/phase2_metrics.py",
    "agent_world_model/phase2_schema.py",
    "agent_world_model/phase2_training.py",
    "agent_world_model/phase3_agent.py",
    "agent_world_model/phase3_candidates.py",
    "agent_world_model/phase3_planning.py",
    "agent_world_model/rate_limiter.py",
    "agent_world_model/reactive_agent.py",
    "agent_world_model/release_fingerprint.py",
    "agent_world_model/remote_agent.py",
    "agent_world_model/state.py",
    "agent_world_model/structure_alignment.py",
    "agent_world_model/trajectory.py",
    "agent_world_model/world_model.py",
    "scripts/evaluate_webarena_online.py",
    "scripts/serve_phase3_inference.py",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files(
    project_root: str | Path,
    ensemble_manifest: str | Path,
    alignment_checkpoint: str | Path,
    planning_config: str | Path,
) -> list[Path]:
    root = Path(project_root).resolve()
    manifest_path = Path(ensemble_manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = [root / item for item in RELEASE_SOURCE_PATHS]
    paths.extend(
        [
            manifest_path,
            Path(alignment_checkpoint).resolve(),
            Path(planning_config).resolve(),
        ]
    )
    paths.extend((root / member["checkpoint"]).resolve() for member in manifest["members"])
    return sorted(set(paths), key=lambda item: item.as_posix())


def release_fingerprint(paths: Iterable[str | Path], *, root: str | Path) -> dict[str, object]:
    resolved_root = Path(root).resolve()
    records = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            label = path.relative_to(resolved_root).as_posix()
        except ValueError:
            label = path.name
        records.append({"path": label, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    records.sort(key=lambda item: str(item["path"]))
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "files": records,
    }
