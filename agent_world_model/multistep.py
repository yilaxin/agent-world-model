"""Observed contiguous trajectory windows for H=1--3 evaluation."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Sequence


def _terminal(record: Mapping[str, Any]) -> bool:
    signals = record.get("task_signals")
    if isinstance(signals, Mapping):
        return float(signals.get("terminal", 0.0)) >= 0.5
    return bool(record.get("done") or record.get("terminated") or record.get("truncated"))


def _risk(record: Mapping[str, Any], name: str) -> bool:
    risks = record.get("risks")
    if isinstance(risks, Mapping):
        return float(risks.get(name, 0.0)) >= 0.5
    labels = record.get("labels")
    if isinstance(labels, Mapping):
        source_name = "task_success" if name == "success" else name
        return bool(labels.get(source_name, False))
    return False


def _invalid(record: Mapping[str, Any]) -> bool:
    signals = record.get("task_signals")
    if isinstance(signals, Mapping):
        return float(signals.get("invalid_action", 0.0)) >= 0.5
    labels = record.get("labels")
    return bool(labels.get("invalid_action", False)) if isinstance(labels, Mapping) else False


def build_horizon_windows(
    records: Iterable[Mapping[str, Any]], *, max_horizon: int = 3
) -> dict[int, list[list[Mapping[str, Any]]]]:
    """Group truly contiguous steps without crossing episodes or terminals."""

    if not 1 <= max_horizon <= 3:
        raise ValueError("max_horizon must be in [1, 3]")
    episodes: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        episode_id = str(record.get("episode_id") or record.get("run_id") or "")
        if not episode_id:
            continue
        episodes[episode_id].append(record)
    windows: dict[int, list[list[Mapping[str, Any]]]] = {
        horizon: [] for horizon in range(1, max_horizon + 1)
    }
    for episode_records in episodes.values():
        ordered = sorted(episode_records, key=lambda row: int(row.get("step_index", 0)))
        for start in range(len(ordered)):
            for horizon in range(1, max_horizon + 1):
                window = ordered[start : start + horizon]
                if len(window) != horizon:
                    continue
                indices = [int(row.get("step_index", 0)) for row in window]
                if indices != list(range(indices[0], indices[0] + horizon)):
                    continue
                if any(_terminal(row) for row in window[:-1]):
                    continue
                windows[horizon].append(window)
    return windows


def multistep_coverage_summary(
    windows: Mapping[int, Sequence[Sequence[Mapping[str, Any]]]],
) -> dict[str, Any]:
    """Summarise real trajectory and rare-outcome coverage by horizon."""

    by_horizon: dict[str, dict[str, Any]] = {}
    all_rows: list[Sequence[Mapping[str, Any]]] = []
    for horizon in sorted(windows):
        rows = list(windows[horizon])
        all_rows.extend(rows)
        task_counts = Counter(str(row[0].get("task_id", "")) for row in rows)
        by_horizon[str(horizon)] = {
            "window_count": len(rows),
            "task_count": len(task_counts),
            "terminal_ending_count": sum(_terminal(row[-1]) for row in rows),
            "success_ending_count": sum(_risk(row[-1], "success") for row in rows),
            "severe_failure_ending_count": sum(
                _risk(row[-1], "severe_failure") for row in rows
            ),
            "invalid_action_window_count": sum(
                any(_invalid(step) for step in row) for row in rows
            ),
        }
    long_rows = [row for horizon, rows in windows.items() if horizon >= 2 for row in rows]
    return {
        "by_horizon": by_horizon,
        "total_window_count": len(all_rows),
        "long_horizon_window_count": len(long_rows),
        "long_horizon_terminal_count": sum(_terminal(row[-1]) for row in long_rows),
        "long_horizon_severe_failure_count": sum(
            _risk(row[-1], "severe_failure") for row in long_rows
        ),
        "quality_gates": {
            "h2_windows_ge_100": len(windows.get(2, [])) >= 100,
            "h3_windows_ge_100": len(windows.get(3, [])) >= 100,
            "long_horizon_terminal_ge_25": sum(
                _terminal(row[-1]) for row in long_rows
            )
            >= 25,
            "long_horizon_severe_failure_ge_10": sum(
                _risk(row[-1], "severe_failure") for row in long_rows
            )
            >= 10,
        },
    }
