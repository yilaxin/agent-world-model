#!/usr/bin/env python3
"""Archive formal WebArena trajectories beside their machine-readable reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--wsl-distro", default="Ubuntu-24.04")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories_webarena_formal_evidence",
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _source_path(raw: str, distro: str) -> Path:
    path = Path(raw)
    if path.exists():
        return path
    if raw.startswith("/"):
        return Path(f"\\\\wsl.localhost\\{distro}") / raw.lstrip("/").replace(
            "/", "\\"
        )
    return _resolve(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_trajectory(path: Path, row: dict[str, Any]) -> None:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = int(row["attempted_actions"])
    if len(records) != expected:
        raise ValueError(
            f"trajectory/report action count mismatch: {path} has {len(records)}, "
            f"report says {expected}"
        )
    if any(int(record["seed"]) != int(row["seed"]) for record in records):
        raise ValueError(f"trajectory seed mismatch: {path}")
    if any(str(record["env_id"]) != str(row["env_id"]) for record in records):
        raise ValueError(f"trajectory environment mismatch: {path}")


def main() -> int:
    args = parse_args()
    output_dir = _resolve(args.output_dir)
    archived: set[Path] = set()
    summary: list[dict[str, Any]] = []
    for raw_report_path in args.report:
        report_path = _resolve(raw_report_path)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for mode in ("reactive", "world-model"):
            for row in report.get("results", {}).get(mode, []):
                source = _source_path(str(row["trajectory_path"]), args.wsl_distro)
                if not source.is_file():
                    raise FileNotFoundError(f"trajectory is unavailable: {source}")
                relative = Path(str(row["site"])) / mode / (
                    f"task{int(row['task_id'])}_seed{int(row['seed'])}.jsonl"
                )
                destination = output_dir / relative
                if destination in archived:
                    raise ValueError(f"duplicate trajectory destination: {destination}")
                archived.add(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                _validate_trajectory(destination, row)
                digest = _sha256(destination)
                row["trajectory_path"] = destination.relative_to(PROJECT_ROOT).as_posix()
                row["trajectory_sha256"] = digest
                summary.append(
                    {
                        "mode": mode,
                        "site": row["site"],
                        "task_id": row["task_id"],
                        "seed": row["seed"],
                        "bytes": destination.stat().st_size,
                        "sha256": digest,
                    }
                )
        report["trajectories_archived_in_workspace"] = True
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "archived_trajectories": len(summary),
                "total_bytes": sum(item["bytes"] for item in summary),
                "items": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
