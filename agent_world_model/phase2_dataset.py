"""Dataset building, leakage-safe splitting and phase-two data audits."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .counterfactual import counterfactual_pair_summary
from .multistep import build_horizon_windows, multistep_coverage_summary
from .phase2_schema import Phase2Example, canonicalize_transition
from .trajectory import iter_trajectory


def _episode_order(episode_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{episode_id}".encode("utf-8")).hexdigest()


def split_episodes(
    episode_ids: Sequence[str],
    *,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, str]:
    """Assign whole episodes to splits so adjacent steps never leak."""

    unique = sorted(set(episode_ids), key=lambda item: _episode_order(item, seed))
    if not unique:
        return {}
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1")
    if not 0.0 <= validation_ratio < 1.0:
        raise ValueError("validation_ratio must be in [0, 1)")
    if train_ratio + validation_ratio >= 1.0:
        raise ValueError("train_ratio + validation_ratio must be below 1")

    count = len(unique)
    train_count = max(1, round(count * train_ratio))
    validation_count = round(count * validation_ratio)
    if count >= 3:
        validation_count = max(1, validation_count)
        train_count = min(train_count, count - 2)
    elif count == 2:
        train_count, validation_count = 1, 1
    else:
        train_count, validation_count = 1, 0

    result: dict[str, str] = {}
    for index, episode_id in enumerate(unique):
        if index < train_count:
            split = "train"
        elif index < train_count + validation_count:
            split = "validation"
        else:
            split = "test"
        result[episode_id] = split
    return result


def discover_trajectory_files(paths: Iterable[str | Path]) -> list[Path]:
    files: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files.update(item for item in path.rglob("*.jsonl") if item.is_file())
        elif path.is_file():
            files.add(path)
    return sorted(files)


def load_phase2_examples(
    paths: Iterable[str | Path],
    *,
    state_dimensions: int = 512,
    action_dimensions: int = 128,
    seed: int = 42,
) -> tuple[list[Phase2Example], list[Path]]:
    files = discover_trajectory_files(paths)
    records: list[Mapping[str, Any]] = []
    for path in files:
        records.extend(iter_trajectory(path))
    preliminary = [
        canonicalize_transition(
            record,
            state_dimensions=state_dimensions,
            action_dimensions=action_dimensions,
        )
        for record in records
    ]
    split_group_by_episode = {
        example.episode_id: str(
            example.metadata.get("counterfactual_group_id") or example.episode_id
        )
        for example in preliminary
    }
    assignments = split_episodes(
        list(split_group_by_episode.values()), seed=seed
    )
    return [
        replace(
            example,
            split=assignments[split_group_by_episode[example.episode_id]],
        )
        for example in preliminary
    ], files


def write_jsonl(path: str | Path, examples: Iterable[Phase2Example]) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as file:
        for example in examples:
            file.write(
                json.dumps(example.to_dict(), ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
            count += 1
    return count


def read_phase2_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def audit_examples(
    examples: Sequence[Phase2Example],
    *,
    source_files: Sequence[Path] = (),
) -> dict[str, Any]:
    split_counts = Counter(example.split for example in examples)
    task_counts = Counter(example.task_id for example in examples)
    action_counts = Counter(example.action_type for example in examples)
    label_sources = Counter(example.label_source for example in examples)
    duplicate_count = len(examples) - len({example.example_id for example in examples})
    episodes_by_split: dict[str, set[str]] = {
        "train": set(),
        "validation": set(),
        "test": set(),
    }
    for example in examples:
        episodes_by_split.setdefault(example.split, set()).add(example.episode_id)
    leakage = sorted(
        (episodes_by_split.get("train", set()) & episodes_by_split.get("validation", set()))
        | (episodes_by_split.get("train", set()) & episodes_by_split.get("test", set()))
        | (
            episodes_by_split.get("validation", set())
            & episodes_by_split.get("test", set())
        )
    )
    vector_dimensions = sorted({len(example.state_vector) for example in examples})
    action_dimensions = sorted({len(example.action_vector) for example in examples})
    p0_minimum = 500
    p1_minimum = 3000
    tracked_risks = ("success", "stalled", "goal_deviation", "severe_failure")
    tracked_signals = ("invalid_action", "terminal")
    positive_counts = {
        name: int(sum(example.risks.get(name, 0.0) >= 0.5 for example in examples))
        for name in tracked_risks
    } | {
        name: int(
            sum(example.task_signals.get(name, 0.0) >= 0.5 for example in examples)
        )
        for name in tracked_signals
    }
    positive_by_split = {
        split: {
            name: int(
                sum(
                    example.split == split
                    and (
                        example.risks.get(name, 0.0)
                        if name in tracked_risks
                        else example.task_signals.get(name, 0.0)
                    )
                    >= 0.5
                    for example in examples
                )
            )
            for name in (*tracked_risks, *tracked_signals)
        }
        for split in ("train", "validation", "test")
    }
    counterfactual_pairs: dict[str, list[Phase2Example]] = defaultdict(list)
    for example in examples:
        pair_id = str(example.metadata.get("counterfactual_pair_id", ""))
        if pair_id:
            counterfactual_pairs[pair_id].append(example)
    valid_counterfactual_pairs = {
        pair_id
        for pair_id, pair in counterfactual_pairs.items()
        if {str(item.metadata.get("counterfactual_role", "")) for item in pair}
        == {"factual", "counterfactual"}
        and len({str(item.metadata.get("initial_state_id", "")) for item in pair}) == 1
        and all(bool(item.metadata.get("observed_in_environment")) for item in pair)
    }
    counterfactual_split_leakage = sorted(
        pair_id
        for pair_id, pair in counterfactual_pairs.items()
        if len({item.split for item in pair}) > 1
    )
    counterfactual_groups: dict[str, list[Phase2Example]] = defaultdict(list)
    for example in examples:
        group_id = str(example.metadata.get("counterfactual_group_id", ""))
        if group_id:
            counterfactual_groups[group_id].append(example)
    counterfactual_group_split_leakage = sorted(
        group_id
        for group_id, group in counterfactual_groups.items()
        if len({item.split for item in group}) > 1
    )
    counterfactual_by_split = {
        split: counterfactual_pair_summary(
            [example for example in examples if example.split == split]
        )
        for split in ("train", "validation", "test")
    }
    counterfactual_overall = counterfactual_pair_summary(examples)
    multistep_by_split = {
        split: multistep_coverage_summary(
            build_horizon_windows(
                [
                    example.to_dict()
                    for example in examples
                    if example.split == split
                ]
            )
        )
        for split in ("train", "validation", "test")
    }
    multistep_overall = multistep_coverage_summary(
        build_horizon_windows([example.to_dict() for example in examples])
    )
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_files": [str(path) for path in source_files],
        "transition_count": len(examples),
        "episode_count": len({example.episode_id for example in examples}),
        "task_count": len(task_counts),
        "split_counts": dict(split_counts),
        "task_counts": dict(task_counts),
        "action_type_counts": dict(action_counts),
        "label_source_counts": dict(label_sources),
        "positive_label_counts": positive_counts,
        "positive_label_counts_by_split": positive_by_split,
        "counterfactual_audit": {
            "pair_count": len(counterfactual_pairs),
            "valid_observed_pair_count": len(valid_counterfactual_pairs),
            "observed_transition_count": sum(
                bool(example.metadata.get("observed_in_environment"))
                for example in examples
            ),
            "severe_failure_positive_count": sum(
                example.metadata.get("counterfactual_role") == "counterfactual"
                and example.risks.get("severe_failure", 0.0) >= 0.5
                for example in examples
            ),
            "pair_split_leakage": counterfactual_split_leakage,
            "group_split_leakage": counterfactual_group_split_leakage,
            "overall": counterfactual_overall,
            "by_split": counterfactual_by_split,
        },
        "multistep_audit": {
            "overall": multistep_overall,
            "by_split": multistep_by_split,
        },
        "rare_label_warnings": [
            name for name, count in positive_counts.items() if count < 25
        ],
        "state_vector_dimensions": vector_dimensions,
        "action_vector_dimensions": action_dimensions,
        "duplicate_example_ids": duplicate_count,
        "episode_split_leakage": leakage,
        "quality_gates": {
            "valid_schema": bool(
                examples
                and vector_dimensions == [vector_dimensions[0]]
                and action_dimensions == [action_dimensions[0]]
            ),
            "no_duplicate_ids": duplicate_count == 0,
            "no_episode_leakage": not leakage,
            "p0_500_transitions": len(examples) >= p0_minimum,
            "p1_3000_transitions": len(examples) >= p1_minimum,
            "core_signal_support": all(
                positive_counts[name] >= 25
                for name in ("success", "stalled", "invalid_action", "terminal")
            ),
            "observed_counterfactual_pairs": len(valid_counterfactual_pairs) >= 25,
            "counterfactual_scale_1000": len(valid_counterfactual_pairs) >= 1000,
            "counterfactual_test_informative_200": (
                counterfactual_by_split["test"]["informative_pair_count"] >= 200
            ),
            "counterfactual_tie_rate_le_20pct": (
                counterfactual_overall["informative_rate"] >= 0.80
            ),
            "no_counterfactual_pair_leakage": not counterfactual_split_leakage,
            "no_counterfactual_group_leakage": not counterfactual_group_split_leakage,
            "multistep_h2_test_100": (
                multistep_by_split["test"]["by_horizon"]["2"]["window_count"]
                >= 100
            ),
            "multistep_h3_test_100": (
                multistep_by_split["test"]["by_horizon"]["3"]["window_count"]
                >= 100
            ),
            "multistep_terminal_test_25": (
                multistep_by_split["test"]["long_horizon_terminal_count"] >= 25
            ),
            "multistep_severe_failure_test_10": (
                multistep_by_split["test"]["long_horizon_severe_failure_count"]
                >= 10
            ),
        },
    }


def write_dataset_bundle(
    output_dir: str | Path,
    examples: Sequence[Phase2Example],
    *,
    source_files: Sequence[Path] = (),
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for split in ("train", "validation", "test"):
        write_jsonl(
            output / f"{split}.jsonl",
            (example for example in examples if example.split == split),
        )
    card = audit_examples(examples, source_files=source_files)
    (output / "dataset_card.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return card
