#!/usr/bin/env python3
"""Classify failure modes in the frozen round-2 360-episode WebArena holdout.

The taxonomy follows the project roadmap (P1 "360 轨迹错误诊断"):
task understanding, element location, action execution, loop/stall,
budget exhaustion, missing termination, and evaluator/environment issues.
Every episode receives exactly one primary blocking category; signals are
deterministic and derived only from observable trajectory rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--analysis",
        type=Path,
        default=ROOT / "data/reports/webarena_p0_round2_2x2_analysis.json",
        help="Round-2 2x2 analysis JSON containing episode_evidence.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/reports/webarena_p0_round2_failure_diagnosis.json",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=ROOT / "WEBARENA_P0_ROUND2_FAILURE_DIAGNOSIS.md",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from error
    return rows


def action_type(action: str) -> str:
    return action.split("(", 1)[0].strip() or "unknown"


def target_name(row: dict[str, Any]) -> str:
    decision = row.get("decision") or {}
    if decision.get("target_name"):
        return str(decision["target_name"])
    action = str(row.get("action") or "")
    candidates = decision.get("candidates") or []
    for candidate in candidates:
        if candidate.get("action") == action:
            return str(candidate.get("target_name") or "")
    return ""


def _goal_satisfaction_hint(goal: str, url: str, targets: list[str]) -> bool:
    """Conservative observable-state hint that a task may be complete.

    Only URL/content signals that are directly readable from the goal are
    used.  This is not an evaluator; it feeds the "missing termination"
    category for episodes that reached the requested page but never sent
    ``send_msg_to_user``.
    """
    lowered_goal = goal.lower()
    lowered_url = url.lower()
    joined_targets = " ".join(targets).lower()
    if "wish list" in lowered_goal or "wishlist" in lowered_goal:
        return "/wishlist" in lowered_url
    if "cart" in lowered_goal or "shopping cart" in lowered_goal:
        return "/cart" in lowered_url
    if "todos" in lowered_goal:
        return "/dashboard/todos" in lowered_url
    if "issues" in lowered_goal and "open" in lowered_goal:
        return re.search(r"issues[?/]", lowered_url) is not None
    if "subscribe" in lowered_goal:
        return bool(re.search(r"\bunsubscribe\b", joined_targets)) or "/f/" in lowered_url
    return False


def classify(rows: list[dict[str, Any]]) -> tuple[str, list[str], dict[str, Any]]:
    goals = [str((row.get("state") or {}).get("goal") or "") for row in rows]
    goal = goals[0] if goals else ""
    actions = [str(row.get("action") or "") for row in rows]
    targets = [target_name(row) for row in rows]
    urls = [str((row.get("state") or {}).get("url") or "") for row in rows]
    urls += [str((rows[-1].get("next_state") or {}).get("url") or "")] if rows else []
    errors = [
        str((row.get("next_state") or {}).get("last_action_error") or "")
        for row in rows
    ]
    rewards = [float(row.get("reward") or 0.0) for row in rows]
    action_counts = Counter(actions)
    action_types = Counter(action_type(action) for action in actions)
    repeated_steps = sum(count - 1 for count in action_counts.values() if count > 1)
    error_steps = sum(bool(error) for error in errors)
    timeout_steps = sum("timeout" in error.lower() for error in errors)
    invalid_steps = sum(
        any(token in error.lower() for token in ("invalid", "not found", "detached", "no element"))
        for error in errors
    )
    unique_urls = len(set(urls))
    max_steps = len(rows)
    answer_steps = sum(
        action.startswith("send_msg_to_user(") or action.startswith('send_msg_to_user("Done"')
        for action in actions
    )
    done_submitted = any('"Done"' in action or "Done" in action for action in actions)
    reasons: list[str] = []

    if not rows:
        category = "evaluator_environment"
        reasons.append("轨迹文件没有有效步骤")
    elif invalid_steps >= max(1, max_steps // 4):
        category = "element_location"
        reasons.append(f"{invalid_steps}/{max_steps} 步元素无效、缺失或已脱离页面")
    elif error_steps >= max(3, max_steps // 3):
        category = "action_execution"
        reasons.append(f"{error_steps}/{max_steps} 步返回动作错误，其中超时 {timeout_steps} 步")
    elif repeated_steps >= max(4, max_steps // 2) or (unique_urls <= 2 and repeated_steps >= 3):
        category = "loop_stall"
        reasons.append(f"重复动作 {repeated_steps} 步，唯一 URL 数 {unique_urls}")
    elif max_steps >= 12 and not any(rewards):
        satisfied = _goal_satisfaction_hint(goal, urls[-1] if urls else "", targets)
        if satisfied and not done_submitted:
            category = "missing_termination"
            reasons.append("观察状态已满足目标页面信号，但从未显式提交 Done")
        elif not done_submitted:
            category = "budget_exhausted"
            reasons.append("达到 12 步预算且从未提交答案")
        else:
            category = "task_understanding"
            reasons.append("已提交但官方奖励仍为 0，关键操作序列未完成")
    elif not any(rewards):
        satisfied = _goal_satisfaction_hint(goal, urls[-1] if urls else "", targets)
        if satisfied and not done_submitted:
            category = "missing_termination"
            reasons.append("已到达目标页面/状态但未显式提交 Done")
        else:
            category = "task_understanding"
            reasons.append("动作可执行但未形成满足任务的完整操作序列")
    else:
        category = "task_understanding"
        reasons.append("存在奖励但任务未完成，策略理解或执行序列不完整")

    if action_types.get("click", 0) == max_steps and max_steps >= 4:
        reasons.append("轨迹几乎只包含点击，没有搜索/输入/显式终止")
    if timeout_steps:
        reasons.append(f"共 {timeout_steps} 步点击超时")
    if len(set(targets)) <= 3 and max_steps >= 8:
        reasons.append("候选目标高度集中，探索多样性不足")

    signals = {
        "steps": max_steps,
        "unique_urls": unique_urls,
        "unique_actions": len(action_counts),
        "repeated_action_steps": repeated_steps,
        "action_error_steps": error_steps,
        "timeout_steps": timeout_steps,
        "invalid_or_detached_steps": invalid_steps,
        "explicit_answer_steps": answer_steps,
        "done_submitted": done_submitted,
        "action_types": dict(sorted(action_types.items())),
        "first_action": actions[0] if actions else "",
        "first_target_name": targets[0] if targets else "",
        "last_action": actions[-1] if actions else "",
        "last_target_name": targets[-1] if targets else "",
        "last_url": urls[-1] if urls else "",
    }
    return category, reasons, {"goal": goal, **signals}


CATEGORY_LABELS = {
    "task_understanding": "目标理解/候选缺失",
    "element_location": "元素定位失败",
    "action_execution": "动作执行失败",
    "loop_stall": "循环/停滞",
    "budget_exhausted": "预算耗尽未完成",
    "missing_termination": "缺显式终止/提交",
    "evaluator_environment": "评测/环境异常",
}


def main() -> int:
    args = parse_args()
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    evidence = analysis["episode_evidence"]
    episodes = []
    category_counts: Counter[str] = Counter()
    by_site: dict[str, Counter[str]] = defaultdict(Counter)
    by_cell: dict[str, Counter[str]] = defaultdict(Counter)
    aggregate = Counter()
    action_type_totals: Counter[str] = Counter()

    for item in evidence:
        path = ROOT / str(item["trajectory_path"]).replace(str(ROOT) + "/", "")
        rows = load_rows(path)
        category, reasons, signals = classify(rows)
        category_counts[category] += 1
        by_site[str(item["site"])][category] += 1
        by_cell[str(item["cell"])][category] += 1
        for key in (
            "steps",
            "repeated_action_steps",
            "action_error_steps",
            "timeout_steps",
            "explicit_answer_steps",
        ):
            aggregate[key] += int(signals[key])
        action_type_totals.update(signals["action_types"])
        episodes.append(
            {
                "site": item["site"],
                "cell": item["cell"],
                "mode": item["mode"],
                "task_id": item["task_id"],
                "success": bool(item["success"]),
                "category": category,
                "category_label": CATEGORY_LABELS[category],
                "reasons": reasons,
                "trajectory_path": str(path.relative_to(ROOT)),
                "trajectory_sha256": sha256(path),
                **signals,
            }
        )

    total = len(episodes)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": {
            "type": "deterministic_posthoc_trajectory_diagnosis",
            "unit": "episode",
            "primary_category_is_mutually_exclusive": True,
            "taxonomy": "task_understanding/element_location/action_execution/loop_stall/budget_exhausted/missing_termination/evaluator_environment",
            "uses_task_feedback": False,
            "uses_reference_answers": False,
            "limitations": [
                "该诊断基于可观测轨迹信号，不等价于人工逐帧因果标注。",
                "缺失终止类仅使用 URL/可见控件信号，不读取参考答案。",
            ],
        },
        "source": {
            "analysis": str(args.analysis.relative_to(ROOT)),
            "analysis_sha256": sha256(args.analysis),
            "episode_count": total,
            "freeze_sha256": analysis.get("freeze_sha256"),
            "release_fingerprint_sha256": analysis.get("release_fingerprint_sha256"),
        },
        "summary": {
            "episodes": total,
            "successes": sum(row["success"] for row in episodes),
            "category_counts": {
                CATEGORY_LABELS[key]: value for key, value in category_counts.most_common()
            },
            "category_rates": {
                CATEGORY_LABELS[key]: value / total if total else 0.0
                for key, value in category_counts.most_common()
            },
            "by_site": {
                key: {CATEGORY_LABELS[cat]: n for cat, n in value.most_common()}
                for key, value in sorted(by_site.items())
            },
            "by_cell": {
                key: {CATEGORY_LABELS[cat]: n for cat, n in value.most_common()}
                for key, value in sorted(by_cell.items())
            },
            "aggregate_signals": dict(aggregate),
            "action_type_totals": dict(action_type_totals.most_common()),
        },
        "episodes": episodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# WebArena round-2 P0 轨迹错误类型诊断",
        "",
        f"- 样本：{total} 条冻结未见任务配对轨迹；成功 {report['summary']['successes']} 条。",
        "- 方法：确定性事后诊断；每条轨迹分配一个互斥的第一阻断类别。",
        "- 边界：不使用同题反馈或参考答案；结果不是反事实成功率估计。",
        "",
        "## 总体分布",
        "",
        "| 类别 | 数量 | 比例 |",
        "|---|---:|---:|",
    ]
    for key, value in category_counts.most_common():
        lines.append(f"| {CATEGORY_LABELS[key]} | {value} | {value / total:.1%} |")
    lines += [
        "",
        "## 关键可观测信号",
        "",
        f"- 总动作步数：{aggregate['steps']}；动作错误：{aggregate['action_error_steps']}；点击超时：{aggregate['timeout_steps']}。",
        f"- 重复动作步：{aggregate['repeated_action_steps']}；显式提交/终止：{aggregate['explicit_answer_steps']}。",
        f"- 动作类型：{dict(action_type_totals.most_common())}。",
        "",
        "## 结论与下一步",
        "",
        "1. 先修复目标到候选动作的语义覆盖和显式终止条件，再讨论世界模型重排收益。",
        "2. 为点击超时、重复目标和登出等危险导航加入可观测状态护栏与恢复动作。",
        "3. 在开发集上证明非零 SR 后，再冻结第三套未见任务做 reactive/W4 配对检验。",
    ]
    args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
