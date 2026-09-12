#!/usr/bin/env python3
"""Diff two failure-attribution runs produced by attribute_webarena_failures.py.

Purpose: the W1 inner loop changes one strategy module at a time and needs to
know whether that change fixed the targeted failures, moved them somewhere
else, or traded them for regressions.  Absolute success rates are too noisy at
28 dev episodes to answer that, so this tool reports the paired transition
matrix instead:

* fixed      - failed before, succeeds now
* regressed  - succeeded before, fails now
* recategorised - still failing, but the blocking category changed
* unchanged  - same failure category as before

It also applies the completion rules from W1_BASELINE_STRATEGY_PLAN.md:
the targeted category must drop by at least 40%, no other category may grow by
more than 10%, and the paired success count must not decrease.

Only the intersection of (site, mode, guard, task_id, seed) keys is compared,
so adding or removing tasks between runs cannot silently inflate the result.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_DROP = 0.40
DEFAULT_OTHER_GROWTH = 0.10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="Attribution JSON before the change.")
    parser.add_argument("--candidate", type=Path, required=True, help="Attribution JSON after the change.")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Category the change is supposed to fix (e.g. loop_stall). Repeatable.",
    )
    parser.add_argument("--min-target-drop", type=float, default=DEFAULT_TARGET_DROP)
    parser.add_argument("--max-other-growth", type=float, default=DEFAULT_OTHER_GROWTH)
    parser.add_argument(
        "--max-new-category-episodes",
        type=int,
        default=1,
        help=(
            "How many paired episodes may appear in a category that had zero failures "
            "before. Small dev runs need a little slack, but a brand new failure mode "
            "should still block the gate."
        ),
    )
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-markdown", type=Path, default=None)
    parser.add_argument("--max-examples", type=int, default=10)
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    episodes = payload.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError(f"{path}: missing 'episodes' list; run attribute_webarena_failures.py first")
    return episodes


def episode_key(record: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(record.get("site")),
        str(record.get("mode")),
        str(record.get("guard")),
        str(record.get("task_id")),
        str(record.get("seed")),
    )


def category_of(record: Mapping[str, Any]) -> str:
    return "success" if record.get("success") else str(record.get("category"))


def exact_mcnemar_p(gains: int, losses: int) -> float:
    from math import comb

    total = gains + losses
    if total == 0:
        return 1.0
    tail = sum(comb(total, index) for index in range(0, min(gains, losses) + 1))
    return min(1.0, 2.0 * tail / 2**total)


def _summary_block(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    categories: Counter[str] = Counter()
    successes = 0
    for record in records:
        categories[category_of(record)] += 1
        if record.get("success"):
            successes += 1
    return {
        "episodes": len(records),
        "successes": successes,
        "success_rate": successes / len(records) if records else 0.0,
        "categories": dict(categories.most_common()),
    }


def compare(
    baseline: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
    targets: Iterable[str] = (),
    min_target_drop: float = DEFAULT_TARGET_DROP,
    max_other_growth: float = DEFAULT_OTHER_GROWTH,
    max_new_category_episodes: int = 1,
) -> dict[str, Any]:
    targets = sorted(set(targets))
    base_by_key = {episode_key(record): record for record in baseline}
    cand_by_key = {episode_key(record): record for record in candidate}
    common = sorted(set(base_by_key) & set(cand_by_key))
    only_baseline = sorted(set(base_by_key) - set(cand_by_key))
    only_candidate = sorted(set(cand_by_key) - set(base_by_key))

    transitions: Counter[str] = Counter()
    recategorised: Counter[tuple[str, str]] = Counter()
    fixed: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    for key in common:
        before = base_by_key[key]
        after = cand_by_key[key]
        before_category = category_of(before)
        after_category = category_of(after)
        if before_category == "success" and after_category == "success":
            transitions["still_success"] += 1
        elif before_category != "success" and after_category == "success":
            transitions["fixed"] += 1
            fixed.append(_describe(key, before, after))
        elif before_category == "success" and after_category != "success":
            transitions["regressed"] += 1
            regressed.append(_describe(key, before, after))
        elif before_category == after_category:
            transitions["unchanged_failure"] += 1
        else:
            transitions["recategorised"] += 1
            recategorised[(before_category, after_category)] += 1

    base_summary = _summary_block(baseline)
    cand_summary = _summary_block(candidate)
    paired_base = [base_by_key[key] for key in common]
    paired_cand = [cand_by_key[key] for key in common]
    paired_base_summary = _summary_block(paired_base)
    paired_cand_summary = _summary_block(paired_cand)

    categories = sorted(
        set(paired_base_summary["categories"]) | set(paired_cand_summary["categories"])
    )
    category_deltas: list[dict[str, Any]] = []
    for category in categories:
        if category == "success":
            continue
        before = int(paired_base_summary["categories"].get(category, 0))
        after = int(paired_cand_summary["categories"].get(category, 0))
        change = after - before
        category_deltas.append(
            {
                "category": category,
                "baseline": before,
                "candidate": after,
                "change": change,
                "relative_change": (change / before) if before else None,
                "is_target": category in targets,
            }
        )

    decisions: list[dict[str, Any]] = []
    for entry in category_deltas:
        if not entry["is_target"]:
            continue
        before = entry["baseline"]
        if before == 0:
            decisions.append(
                {
                    "rule": f"target_{entry['category']}_drop",
                    "passed": entry["candidate"] == 0,
                    "detail": "基线为 0，无法计算下降比例" if entry["candidate"] else "基线为 0 且仍为 0",
                }
            )
            continue
        drop = (before - entry["candidate"]) / before
        decisions.append(
            {
                "rule": f"target_{entry['category']}_drop",
                "passed": drop >= min_target_drop,
                "detail": f"下降 {drop:.0%}（要求 ≥ {min_target_drop:.0%}）",
            }
        )
    for entry in category_deltas:
        if entry["is_target"]:
            continue
        if entry["baseline"] == 0:
            decisions.append(
                {
                    "rule": f"new_{entry['category']}_appeared",
                    "passed": entry["candidate"] <= max_new_category_episodes,
                    "detail": (
                        f"基线为 0，候选 {entry['candidate']} 条"
                        f"（允许 ≤ {max_new_category_episodes}）"
                    ),
                }
            )
            continue
        growth = (entry["candidate"] - entry["baseline"]) / entry["baseline"]
        decisions.append(
            {
                "rule": f"other_{entry['category']}_growth",
                "passed": growth <= max_other_growth,
                "detail": f"变化 {growth:+.0%}（要求 ≤ +{max_other_growth:.0%}）",
            }
        )
    paired_gain = paired_cand_summary["successes"] - paired_base_summary["successes"]
    decisions.append(
        {
            "rule": "paired_success_not_lower",
            "passed": paired_gain >= 0,
            "detail": f"配对成功数 {paired_base_summary['successes']} → {paired_cand_summary['successes']}（{paired_gain:+d}）",
        }
    )
    decisions.append(
        {
            "rule": "no_evaluator_environment_failures",
            "passed": int(paired_cand_summary["categories"].get("evaluator_environment", 0)) == 0,
            "detail": f"候选 run 的评测/环境异常 {int(paired_cand_summary['categories'].get('evaluator_environment', 0))} 条",
        }
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "targets": targets,
        "baseline_summary": base_summary,
        "candidate_summary": cand_summary,
        "paired_base_summary": paired_base_summary,
        "paired_candidate_summary": paired_cand_summary,
        "paired_units": len(common),
        "only_in_baseline": [list(key) for key in only_baseline[:50]],
        "only_in_candidate": [list(key) for key in only_candidate[:50]],
        "only_in_baseline_count": len(only_baseline),
        "only_in_candidate_count": len(only_candidate),
        "transitions": dict(transitions),
        "recategorised_flows": [
            {"from": source, "to": destination, "count": count}
            for (source, destination), count in recategorised.most_common()
        ],
        "category_deltas": category_deltas,
        "decisions": decisions,
        "verdict": "PASS" if all(entry["passed"] for entry in decisions) else "FAIL",
        "fixed_examples": fixed[:50],
        "regressed_examples": regressed[:50],
        "mcnemar_p_two_sided": exact_mcnemar_p(
            int(transitions["fixed"]), int(transitions["regressed"])
        ),
    }


def _describe(
    key: tuple[str, str, str, str, str],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "site": key[0],
        "mode": key[1],
        "guard": key[2],
        "task_id": key[3],
        "seed": key[4],
        "goal": (before.get("signals") or {}).get("goal", ""),
        "before_category": category_of(before),
        "after_category": category_of(after),
        "before_reasons": list(before.get("reasons") or [])[:2],
        "after_reasons": list(after.get("reasons") or [])[:2],
        "trajectory": after.get("trajectory_path"),
    }


def render_markdown(result: Mapping[str, Any], max_examples: int) -> str:
    lines: list[str] = []
    lines.append("# 归因差分报告")
    lines.append("")
    lines.append(f"生成时间：{result['generated_at_utc']}")
    lines.append("")
    lines.append(f"**判定：{result['verdict']}**")
    lines.append("")
    lines.append(
        f"配对单元 {result['paired_units']}；基线独有 {result['only_in_baseline_count']}，"
        f"候选独有 {result['only_in_candidate_count']}（不参与配对）。"
    )
    lines.append("")

    lines.append("## 配对迁移")
    lines.append("")
    transitions = result["transitions"]
    lines.append("| 迁移 | 条数 |")
    lines.append("|---|---:|")
    for label, key in (
        ("失败 → 成功（fixed）", "fixed"),
        ("成功 → 失败（regressed）", "regressed"),
        ("失败但类型改变", "recategorised"),
        ("失败且类型不变", "unchanged_failure"),
        ("成功且仍然成功", "still_success"),
    ):
        lines.append(f"| {label} | {int(transitions.get(key, 0))} |")
    lines.append("")
    lines.append(
        f"配对成功数 {result['paired_base_summary']['successes']} → "
        f"{result['paired_candidate_summary']['successes']}；"
        f"McNemar 双侧 p = {result['mcnemar_p_two_sided']:.4f}。"
    )
    lines.append("")

    if result["recategorised_flows"]:
        lines.append("### 失败类型迁移明细")
        lines.append("")
        lines.append("| 从 | 到 | 条数 |")
        lines.append("|---|---|---:|")
        for flow in result["recategorised_flows"][:15]:
            lines.append(f"| `{flow['from']}` | `{flow['to']}` | {flow['count']} |")
        lines.append("")

    lines.append("## 各类型条数变化（配对单元内）")
    lines.append("")
    lines.append("| 类型 | 基线 | 候选 | 变化 | 相对变化 | 目标类型 |")
    lines.append("|---|---:|---:|---:|---:|:--:|")
    for entry in result["category_deltas"]:
        relative = entry["relative_change"]
        relative_text = "—" if relative is None else f"{relative:+.0%}"
        lines.append(
            f"| `{entry['category']}` | {entry['baseline']} | {entry['candidate']} | "
            f"{entry['change']:+d} | {relative_text} | {'是' if entry['is_target'] else ''} |"
        )
    lines.append("")

    lines.append("## 门禁判定")
    lines.append("")
    lines.append("| 规则 | 结果 | 说明 |")
    lines.append("|---|:--:|---|")
    for decision in result["decisions"]:
        lines.append(
            f"| {decision['rule']} | {'PASS' if decision['passed'] else 'FAIL'} | {decision['detail']} |"
        )
    lines.append("")

    if result["regressed_examples"]:
        lines.append(f"## 回退样本（最多 {max_examples} 条）")
        lines.append("")
        for example in result["regressed_examples"][:max_examples]:
            lines.append(
                f"- **{example['site']} · task {example['task_id']} · seed {example['seed']}**："
                f"{example['goal']}"
            )
            lines.append(f"  - 之前成功，现在 `{example['after_category']}`：{'；'.join(example['after_reasons'])}")
        lines.append("")

    if result["fixed_examples"]:
        lines.append(f"## 修复样本（最多 {max_examples} 条）")
        lines.append("")
        for example in result["fixed_examples"][:max_examples]:
            lines.append(
                f"- **{example['site']} · task {example['task_id']} · seed {example['seed']}**"
                f"（原 `{example['before_category']}`）：{example['goal']}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    baseline = load_records(args.baseline)
    candidate = load_records(args.candidate)
    result = compare(
        baseline,
        candidate,
        targets=args.target,
        min_target_drop=args.min_target_drop,
        max_other_growth=args.max_other_growth,
        max_new_category_episodes=args.max_new_category_episodes,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.output_markdown:
        args.output_markdown.write_text(
            render_markdown(result, args.max_examples), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "paired_units": result["paired_units"],
                "transitions": result["transitions"],
                "paired_success": [
                    result["paired_base_summary"]["successes"],
                    result["paired_candidate_summary"]["successes"],
                ],
                "category_deltas": {
                    entry["category"]: [entry["baseline"], entry["candidate"]]
                    for entry in result["category_deltas"]
                },
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
