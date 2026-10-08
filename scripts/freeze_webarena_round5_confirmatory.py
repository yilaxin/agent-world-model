#!/usr/bin/env python3
"""Freeze and pre-register the round-5 confirmatory WebArena holdout.

Why round 5 reuses earlier tasks
--------------------------------
The 812-task Classic WebArena pool is effectively exhausted: after rounds 1-4
plus every dev/recovery run, only 23 GitLab and 17 Shopping non-fuzzy tasks have
never been recorded, and Reddit has none.  A confirmatory design built only on
those 40 tasks reaches 3-35% power for a +10% relative improvement, which cannot
support the proposal's claim.

Round 5 therefore re-uses the tasks that were *frozen holdout* in rounds 2-4
(non-fuzzy evaluators only).  The selection rule is fixed in advance and takes
every such task - no post-hoc choice - and the whole set is written into the
pre-registration record with SHA-256 digests.  Two limitations are disclosed in
the pre-registration and must appear in any report that cites this holdout:

1. these tasks are no longer "never seen" (their outcomes are known from
   earlier rounds), and
2. the v5-v7 strategy improvements were motivated by failure diagnoses run on
   round-2/3 holdout trajectories, so a soft leak exists.

The unseen remainder stays as a secondary, direction-only check.

Design frozen here: three sites, every non-fuzzy task from the rounds 2-4
holdout, seeds 0/1/2, two arms (reactive vs the W4 world-model release, both
with the navigation guard on).  708 paired units.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.freeze_webarena_p0_holdout import _canonical_sha  # noqa: E402
from scripts.prepare_webarena_p0_round3_holdout import _is_fuzzy  # noqa: E402


SALT = "p0-round5-confirmatory-v1"
DEFAULT_SEEDS = [0, 1, 2]
SITES = ["gitlab", "shopping", "reddit"]
RELEASE_FINGERPRINT = "7e34a1e3c74252e8c3ab6ff6b29e2e40eda934e58d27a589c2e528d37c117f32"
REPORT_PATTERN = re.compile(r"webarena_p0_round([234])_holdout_([a-z]+)_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task-source", type=Path, default=ROOT / "tmp/p0_source/test.raw.json"
    )
    parser.add_argument("--report-dir", type=Path, default=ROOT / "data/reports")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "configs")
    parser.add_argument("--preregistration", type=Path, default=ROOT / "ROUND5_PREREGISTRATION.md")
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--step-budget", type=int, default=12)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def repo_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def holdout_evidence(report_dir: Path) -> dict[str, dict[int, set[str]]]:
    """Map site -> task id -> the report files that froze/evaluated it."""
    evidence: dict[str, dict[int, set[str]]] = {site: {} for site in SITES}
    for path in sorted(report_dir.glob("*.json")):
        match = REPORT_PATTERN.match(path.name)
        if not match or ".incomplete_" in path.name:
            continue
        site = match.group(2)
        if site not in evidence:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task_ids: set[int] = set()
        for value in payload.get("fixed_task_ids") or []:
            if str(value).isdigit():
                task_ids.add(int(value))
        for rows in (payload.get("results") or {}).values():
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("task_id") is not None:
                        task_ids.add(int(row["task_id"]))
        for task in task_ids:
            evidence[site].setdefault(task, set()).add(path.relative_to(ROOT).as_posix())
    return evidence


def primary_endpoint_power(units: int, baseline: float, alpha: float = 0.05) -> float:
    """Exact McNemar power for a +10% relative gain, loss ratio 0.3, one-sided."""
    from math import comb, exp, lgamma, log

    def p_value(gains: int, losses: int) -> float:
        total = gains + losses
        if total == 0:
            return 1.0
        tail = sum(comb(total, i) for i in range(0, min(gains, losses) + 1))
        return min(1.0, 2.0 * tail / 2**total)

    gains = units * baseline * 0.10 / (1.0 - 0.3)
    losses = 0.3 * gains
    total_rate = gains + losses
    if total_rate <= 0:
        return 0.0
    q = gains / total_rate
    result = 0.0
    upper = int(total_rate + 8 * max(1.0, total_rate**0.5))
    for total in range(0, upper + 1):
        log_p = -total_rate + total * log(total_rate) - lgamma(total + 1)
        if log_p < -50:
            continue
        inner = 0.0
        for k in range(0, total + 1):
            # one-sided pre-registered test at 0.05 == two-sided 0.10
            if p_value(k, total - k) <= 2 * alpha:
                inner += comb(total, k) * q**k * (1 - q) ** (total - k)
        result += exp(log_p) * inner
    return result


def main() -> int:
    args = parse_args()
    rows = {int(row["task_id"]): row for row in json.loads(args.task_source.read_text(encoding="utf-8"))}
    if len(rows) != 812:
        raise RuntimeError("expected the 812-row Classic WebArena task source")
    evidence = holdout_evidence(args.report_dir)
    frozen_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit = repo_commit()

    site_payloads: dict[str, Any] = {}
    for site in SITES:
        candidates = sorted(evidence[site])
        judgeable = [task for task in candidates if task in rows and not _is_fuzzy(rows[task])]
        if not judgeable:
            raise RuntimeError(f"{site}: no non-fuzzy frozen holdout task available")
        payload: dict[str, Any] = {
            "schema_version": 1,
            "benchmark": f"Classic WebArena P0 round-5 confirmatory ({site})",
            "frozen_at_utc": frozen_at,
            "selection_salt": SALT,
            "required_sites": [site],
            "task_ids": judgeable,
            "task_sites": {str(task): site for task in judgeable},
            "seeds": list(args.seeds),
            "reactive_step_budget": args.step_budget,
            "world_model_step_budget": args.step_budget,
            "episode_max_attempts": 3,
            "task_feedback_used": False,
            "post_freeze_policy_changes_allowed": False,
            "eligible_for_final_claim": True,
            "evaluator_smoke_step_budget": 1,
            "evaluator_smoke_answers": {},
            "release_fingerprint_sha256": RELEASE_FINGERPRINT,
            "arms": {
                "reactive": {"mode": "reactive", "navigation_guard": "on"},
                "world_model": {"mode": "world-model", "navigation_guard": "on"},
            },
            "task_evidence": {str(task): sorted(evidence[site][task]) for task in judgeable},
            "selection_rule": (
                "Every non-fuzzy task frozen as holdout in rounds 2-4 for this site. "
                "The rule is exhaustive, so no task was chosen after seeing results."
            ),
            "scope_limit": (
                "Re-used frozen holdout tasks; not a never-seen set. Paired comparison "
                "is valid because both arms are re-run on the same tasks and seeds."
            ),
        }
        payload["freeze_sha256"] = _canonical_sha(payload)
        path = args.output_dir / f"webarena_p0_round5_confirmatory_{site}_frozen.json"
        if path.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite {path}; pass --force to replace")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        site_payloads[site] = {
            "tasks": len(judgeable),
            "config": path.relative_to(ROOT).as_posix(),
            "freeze_sha256": payload["freeze_sha256"],
        }
        print(f"{site}: {len(judgeable)} tasks frozen -> {path.name}")
        print(f"    freeze_sha256 {payload['freeze_sha256']}")

    units = sum(entry["tasks"] for entry in site_payloads.values()) * len(args.seeds)
    units_two_site = (
        site_payloads["gitlab"]["tasks"] + site_payloads["shopping"]["tasks"]
    ) * len(args.seeds)
    power_table = {
        f"baseline_{int(p * 100)}pct": round(primary_endpoint_power(units, p), 4)
        for p in (0.12, 0.20, 0.30, 0.40)
    }

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "benchmark": "Classic WebArena P0 round-5 confirmatory holdout (3 sites, paired 2-arm)",
        "frozen_at_utc": frozen_at,
        "selection_salt": SALT,
        "repo_commit": commit,
        "sites": SITES,
        "seeds": list(args.seeds),
        "arms": ["reactive", "world-model"],
        "navigation_guard": "on",
        "step_budget": args.step_budget,
        "tasks_per_site": {site: entry["tasks"] for site, entry in site_payloads.items()},
        "site_configs": {site: entry["config"] for site, entry in site_payloads.items()},
        "site_freeze_sha256": {site: entry["freeze_sha256"] for site, entry in site_payloads.items()},
        "paired_units_total": units,
        "paired_units_gitlab_shopping": units_two_site,
        "preregistered_analysis": {
            "primary_endpoint": "paired task success (binary, per task x seed)",
            "test": "exact McNemar, one-sided, alpha 0.05, pre-registered direction (world-model >= reactive)",
            "target_effect": ">= +10% relative success rate vs reactive",
            "power_target": 0.8,
            "strata": "site; sensitivity analysis excluding reddit is reported",
            "secondary_endpoints": [
                "absolute percentage-point difference with 95% CI",
                "action-level failure attribution deltas",
                "unseen-only (40 task) direction check",
            ],
            "power_at_units": power_table,
        },
        "disclosures": [
            "Tasks re-used from rounds 2-4 frozen holdouts; they are not never-seen.",
            "v5-v7 strategy work was motivated by failure diagnoses on round-2/3 holdout trajectories (soft leak).",
            "Only 40 non-fuzzy tasks remain unused anywhere; they are reported as a secondary direction check.",
        ],
        "scope_limit": (
            "Confirmatory paired holdout over re-used frozen tasks. Establishes the "
            "policy comparison, not an unseen-task generalization claim."
        ),
    }
    manifest["freeze_sha256"] = _canonical_sha(manifest)
    manifest_path = args.output_dir / "webarena_p0_round5_confirmatory_frozen.json"
    if manifest_path.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {manifest_path}")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest -> {manifest_path.name}")
    print(f"paired units: total {units}, gitlab+shopping {units_two_site}")
    print(f"preregistered power: {json.dumps(power_table)}")

    lines = [
        "# Round-5 确认性 holdout 预登记",
        "",
        f"- 登记时间（UTC）：{frozen_at}",
        f"- 仓库提交：`{commit}`",
        f"- 选择盐：`{SALT}`",
        f"- 清单：`{manifest_path.relative_to(ROOT).as_posix()}`（freeze_sha256 `{manifest['freeze_sha256']}`）",
        "",
        "## 设计（结果出来前写死）",
        "",
        f"- 站点：{', '.join(SITES)}",
        f"- 任务：Round-2/3/4 冻结 holdout 中评测器非 `fuzzy_match` 的全部任务，共 "
        f"{sum(entry['tasks'] for entry in site_payloads.values())} 道（GitLab "
        f"{site_payloads['gitlab']['tasks']}、Shopping {site_payloads['shopping']['tasks']}、"
        f"Reddit {site_payloads['reddit']['tasks']}），规则穷举、不做挑选",
        f"- seed：{args.seeds}",
        "- 臂：reactive（护栏开）vs W4 世界模型发布版（护栏开），同一任务同一 seed 配对",
        f"- 配对单元：{units}（仅 GitLab+Shopping 为 {units_two_site}）",
        f"- 步数预算：{args.step_budget}",
        "",
        "## 主分析（预登记）",
        "",
        "- 主指标：配对任务成功率（每个 任务×seed 一个二元单元）",
        "- 检验：精确 McNemar，**单侧** α=0.05，方向预登记为 world-model ≥ reactive",
        "- 目标效应：相对提升 ≥ +10%",
        "- 功效目标：0.8",
        "- 分层：按站点；同时报告剔除 Reddit 的敏感性分析",
        "",
        "| 基线成功率 | 该设计功效（+10% 相对提升、损失比 0.3） |",
        "|---|---:|",
    ]
    for key, value in power_table.items():
        lines.append(f"| {key.replace('baseline_', '').replace('pct', '%')} | {value:.0%} |")
    lines += [
        "",
        "## 必须披露的三件事",
        "",
        "1. 任务来自早期轮次的**冻结 holdout 复用**，不再是「从未见过」的集合。",
        "2. v5–v7 的策略改进由 Round-2/3 holdout 轨迹的失败诊断驱动，存在**软泄漏**。",
        "3. 全项目仅剩 40 道从未使用过的非 fuzzy 任务，作为**次要方向性检查**一并报告，不单独用于声称 +10%。",
        "",
        "## 为什么必须复用",
        "",
        "只用未见过任务（40 道 × 3 seed = 120 单元）在 12%–40% 基线下功效仅 3%–35%，"
        "无法支撑 +10% 的声称；复用后 708 单元在 20%–40% 基线下功效达 85%–99%。",
        "",
    ]
    if args.preregistration.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {args.preregistration}")
    args.preregistration.write_text("\n".join(lines), encoding="utf-8")
    print(f"pre-registration -> {args.preregistration.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
