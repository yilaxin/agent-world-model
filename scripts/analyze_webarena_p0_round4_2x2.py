"""Analyse the frozen round-4 WebArena P0 2x2 holdout.

Round-4 covers GitLab and Shopping (Reddit's locally judgeable pool is
exhausted), 40 unseen tasks per site, three frozen seeds (0/1/2), four cells
per site: Reactive/W4 x navigation guard off/on.  This script only reads the
completed cell reports; it cannot change the policy, model weights, task set,
or budgets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SITES = ("gitlab", "shopping")
CELL_SPECS = {
    "reactive_guard_off": ("reactive", "off"),
    "reactive_guard_on": ("reactive", "on"),
    "w4_guard_off": ("world-model", "off"),
    "w4_guard_on": ("world-model", "on"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-dir", type=Path, default=ROOT / "data" / "reports"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs" / "webarena_p0_round4_holdout_frozen.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "reports" / "webarena_p0_round4_2x2_analysis.json",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20_260_819)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilson(successes: int, episodes: int) -> list[float]:
    if episodes == 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    p = successes / episodes
    denom = 1 + z * z / episodes
    centre = (p + z * z / (2 * episodes)) / denom
    half = z * math.sqrt(p * (1 - p) / episodes + z * z / (4 * episodes * episodes)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _load_cell(report_dir: Path, site: str, mode: str, guard: str) -> dict[int, dict[int, bool]]:
    path = report_dir / f"webarena_p0_round4_holdout_{site}_{mode}_guard_{guard}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("results", {}).get(mode, [])
    if payload.get("failures"):
        raise ValueError(f"cell report has evaluator failures: {path}")
    by_task: dict[int, dict[int, bool]] = {}
    for row in rows:
        by_task.setdefault(int(row["task_id"]), {})[int(row["seed"])] = bool(row["success"])
    return by_task


def _paired_ci(
    diffs: list[float],
    rng: random.Random,
    samples: int,
) -> list[float]:
    if not diffs:
        return [0.0, 0.0]
    means: list[float] = []
    for _ in range(samples):
        total = 0.0
        for value in diffs:
            total += value if rng.random() < 0.5 else 0.0
        means.append(total / len(diffs))
    means.sort()
    return [means[int(0.025 * len(means))], means[int(0.975 * len(means))]]


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    seeds = list(manifest["seeds"])
    rng = random.Random(args.bootstrap_seed)

    cells: dict[str, dict[str, dict[int, dict[int, bool]]]] = {}
    per_cell_metrics: dict[str, dict[str, Any]] = {}
    for site in SITES:
        cells[site] = {}
        for cell, (mode, guard) in CELL_SPECS.items():
            by_task = _load_cell(args.report_dir, site, mode, guard)
            expected = int(manifest["tasks_per_site"][site])
            if len(by_task) != expected:
                raise ValueError(f"{site}/{cell}: expected {expected} tasks, got {len(by_task)}")
            for task, seed_map in by_task.items():
                if sorted(seed_map) != seeds:
                    raise ValueError(f"{site}/{cell}: seed mismatch for task {task}")
            episodes = sum(len(seed_map) for seed_map in by_task.values())
            successes = sum(
                sum(seed_map.values()) for seed_map in by_task.values()
            )
            per_cell_metrics[f"{site}/{cell}"] = {
                "episodes": episodes,
                "successes": successes,
                "success_rate": successes / episodes if episodes else 0.0,
                "success_rate_95ci_wilson": _wilson(successes, episodes),
            }
            cells[site][cell] = by_task

    paired: dict[str, Any] = {}
    for site in SITES:
        site_paired: dict[str, Any] = {}
        base = cells[site]
        tasks = sorted(base["reactive_guard_off"])
        for label, left, right in (
            ("w4_minus_reactive_guard_off", "reactive_guard_off", "w4_guard_off"),
            ("w4_minus_reactive_guard_on", "reactive_guard_on", "w4_guard_on"),
            ("guard_effect_reactive", "reactive_guard_off", "reactive_guard_on"),
            ("guard_effect_w4", "w4_guard_off", "w4_guard_on"),
            ("interaction_did", "reactive_guard_off", "w4_guard_on"),
        ):
            diffs: list[float] = []
            for task in tasks:
                for seed in seeds:
                    diffs.append(
                        float(base[right][task][seed])
                        - float(base[left][task][seed])
                    )
            site_paired[label] = {
                "paired_units": len(diffs),
                "mean_improvement_points": 100.0 * statistics.mean(diffs),
                "mean_improvement_95ci_points": [
                    100.0 * value for value in _paired_ci(diffs, rng, args.bootstrap_samples)
                ],
            }
        site_paired["relative_sr_w4_guard_on_vs_reactive_guard_on"] = _relative_sr(
            base["reactive_guard_on"],
            base["w4_guard_on"],
            seeds,
        )
        paired[site] = site_paired

    pool_left = {cell: {} for cell in CELL_SPECS}
    for site in SITES:
        for cell in CELL_SPECS:
            for task, seed_map in cells[site][cell].items():
                pool_left[cell].setdefault((site, task), {})[tuple(seeds)] = {
                    seed: seed_map[seed] for seed in seeds
                }
    pool_diffs = {
        label: [
            float(pool_left[right][key][tuple(seeds)][seed])
            - float(pool_left[left][key][tuple(seeds)][seed])
            for key in sorted(pool_left[right])
            for seed in seeds
        ]
        for label, left, right in (
            ("w4_minus_reactive_guard_off", "reactive_guard_off", "w4_guard_off"),
            ("w4_minus_reactive_guard_on", "reactive_guard_on", "w4_guard_on"),
            ("guard_effect_reactive", "reactive_guard_off", "reactive_guard_on"),
            ("guard_effect_w4", "w4_guard_off", "w4_guard_on"),
            ("interaction_did", "reactive_guard_off", "w4_guard_on"),
        )
    }
    pooled = {
        label: {
            "paired_units": len(diffs),
            "mean_improvement_points": 100.0 * statistics.mean(diffs),
            "mean_improvement_95ci_points": [
                100.0 * value for value in _paired_ci(diffs, rng, args.bootstrap_samples)
            ],
        }
        for label, diffs in pool_diffs.items()
    }

    output = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": "Classic WebArena P0 round-4 unseen paired holdout",
        "manifest": args.manifest.relative_to(ROOT).as_posix(),
        "manifest_sha256": _sha256(args.manifest),
        "freeze_sha256": manifest["freeze_sha256"],
        "sites": list(SITES),
        "seeds": seeds,
        "cell_metrics": per_cell_metrics,
        "paired_per_site": paired,
        "paired_pooled": pooled,
        "scope_limit": (
            "Two-site (GitLab/Shopping) 80-task holdout with seeds 0/1/2; Reddit "
            "was excluded because its locally judgeable pool is exhausted. Not the "
            "full 812-task benchmark."
        ),
        "claim_rule": "Report absolute pp, relative SR, and paired CI; claim +10% only if established on this frozen holdout.",
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _relative_sr(
    reactive: dict[int, dict[int, bool]],
    w4: dict[int, dict[int, bool]],
    seeds: list[int],
) -> dict[str, Any]:
    r_succ = sum(sum(m.values()) for m in reactive.values())
    w_succ = sum(sum(m.values()) for m in w4.values())
    r_eps = sum(len(m) for m in reactive.values())
    w_eps = sum(len(m) for m in w4.values())
    return {
        "reactive_success_rate": r_succ / r_eps if r_eps else 0.0,
        "w4_success_rate": w_succ / w_eps if w_eps else 0.0,
        "absolute_improvement_points": 100.0 * (w_succ / w_eps - r_succ / r_eps)
        if w_eps and r_eps
        else 0.0,
        "relative_improvement": (w_succ / w_eps - r_succ / r_eps) / (r_succ / r_eps)
        if r_eps and r_succ > 0
        else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
