#!/usr/bin/env python3
"""Action-level failure attribution for the frozen WebArena P0 holdout rounds.

The roadmap's P1 item ("360 轨迹错误诊断") only covered round 2 and only
categorised whole episodes.  This tool generalises that diagnosis so the
baseline-strategy work (workstream W1) has a per-step, evidence-backed view of
*why* episodes fail and *which module* owns the fix.

Design constraints:

* Pure standard library, so it runs in the WSL evaluation environment and on
  any machine that only has CPython.
* Frozen artefacts are read-only: the tool never rewrites reports or
  trajectories.
* Numbers are taken from the official cell reports when available, so retried
  episodes do not inflate the corpus.  A raw directory scan is offered as a
  fallback for in-flight rounds that have no report yet.
* Every category is derived from observable trajectory fields: executed
  action, decision metadata, action errors, visited URLs and whether an answer
  was submitted.

Primary output is a machine-readable JSON plus a Markdown summary.  An optional
self-contained HTML view embeds the same records so the failure distribution
can be filtered by round, site, cell and category while iterating on a fix.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

# Primary category -> human label + the module that owns the fix.
CATEGORIES: dict[str, dict[str, str]] = {
    "loop_stall": {
        "label": "循环/停滞",
        "module": "循环恢复（loop recovery）",
    },
    "element_location": {
        "label": "元素定位失败",
        "module": "候选生成与元素定位（AXTree/DOM 剪枝、grounding）",
    },
    "action_execution": {
        "label": "动作执行失败",
        "module": "动作执行鲁棒性（超时、重试、等待策略）",
    },
    "missing_termination": {
        "label": "缺显式终止",
        "module": "终止策略（观察态已满足但未提交答案）",
    },
    "form_or_search_incomplete": {
        "label": "表单/搜索流程不完整",
        "module": "表单与搜索模块（构造查询、提交、校验）",
    },
    "wrong_route": {
        "label": "流程路径错误",
        "module": "站点流程知识（进入目标页面/流程）",
    },
    "candidate_missing": {
        "label": "候选缺失/语义失配",
        "module": "候选生成（候选集合未包含目标元素）",
    },
    "budget_exhausted": {
        "label": "预算耗尽",
        "module": "候选优先级与探索效率",
    },
    "task_understanding": {
        "label": "目标理解偏差",
        "module": "任务解析与子目标分解",
    },
    "evaluator_environment": {
        "label": "评测/环境异常",
        "module": "评测链路（非策略因素，需单独处理）",
    },
}

CATEGORY_ORDER = list(CATEGORIES)

# Goal phrase -> URL fragments that indicate the task reached the relevant
# section.  Phrases are matched as substrings against the lower-cased goal, so
# they must stay specific: "project" alone would match repository names such as
# "a11yproject" and mislabel a commit-counting task as project creation.
# Rules are only used to separate "reached the section but never terminated"
# from "never reached the section at all"; they are supporting evidence, not an
# evaluator.
SITE_EXPECTATIONS: dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "gitlab": [
        (
            (
                "new project",
                "create a project",
                "create a new project",
                "create new project",
                "new repository",
                "empty repository",
                "create a repository",
                "set up a new repository",
            ),
            ("/projects/new",),
        ),
        (
            ("new issue", "create an issue", "open an issue", "open a new issue", "raise an issue", "file an issue"),
            ("/issues/new", "/-/issues/new"),
        ),
        (("issue",), ("/-/issues", "/issues")),
        (("merge request",), ("/-/merge_requests", "/merge_requests")),
        (("to-do", "todo list", "to do list", "todos"), ("/dashboard/todos",)),
        (
            ("invite", "as a guest", "as a member", "add member", "add user", "add a user"),
            ("/project_members", "/-/project_members", "/members"),
        ),
        (("new group", "create a group", "create a new group"), ("/groups/new",)),
        (("commit",), ("/commits", "/-/commits")),
        (("label",), ("/-/labels", "/labels")),
        (("milestone",), ("/-/milestones", "/milestones")),
        (("snippet",), ("/-/snippets", "/snippets")),
        (("upload", "add a file", "add file"), ("/uploads", "/-/new", "/edit")),
    ],
    "shopping": [
        (("cart",), ("/cart",)),
        (("wish list", "wishlist"), ("/wishlist",)),
        (("order", "invoice", "refund", "shipped", "track"), ("/sales/order", "/order/", "/orders")),
        (("review",), ("/review", "/product")),
        (("compare",), ("/catalog/product_compare",)),
        (("coupon", "discount"), ("/cart", "/coupon", "/checkout")),
        (("search", "find", "look for"), ("/catalogsearch", "/search")),
        (
            ("account", "address", "profile", "newsletter", "sign up", "log in", "logged in"),
            ("/customer", "/account", "/newsletter"),
        ),
        (("checkout", "purchase", "buy", "place the order"), ("/checkout", "/cart")),
        (("category", "product list"), ("/catalog", "/category", "/shop")),
    ],
    "reddit": [
        (("submit a post", "create a post", "new post", "write a post"), ("/submit",)),
        (("comment", "reply"), ("/comment", "/r/")),
        (("subscribe", "unsubscribe"), ("/subscribe", "/r/")),
        (("message", "mail"), ("/message", "/mail")),
        (("profile", "user"), ("/user/", "/u/")),
        (("search",), ("/search",)),
    ],
}

FORM_INTENT_TOKENS = (
    "enter",
    "fill",
    "type",
    "set ",
    "add ",
    "create",
    "search",
    "find",
    "filter",
    "look for",
    "select",
    "choose",
    "write",
    "post",
    "submit",
    "name",
    "price",
    "quantity",
    "address",
    "email",
    "title",
    "description",
    "comment",
    "message",
    "review",
)

SUBMIT_ACTION_MARKERS = (
    "send_msg_to_user",
    "press(\"enter\")",
    "press('enter')",
)

INVALID_ERROR_TOKENS = (
    "invalid",
    "not found",
    "detached",
    "no element",
    "unknown element",
    "element is not",
    "stale",
)

ENVIRONMENT_ERROR_TOKENS = (
    "net::err",
    "connection refused",
    "target closed",
    "browser has been closed",
    "page crashed",
    "timeout 90000ms exceeded",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=REPO_ROOT / "data" / "reports",
        help="Directory holding the official cell reports.",
    )
    parser.add_argument(
        "--report-glob",
        default="webarena_p0_round*_holdout_*.json",
        help="Glob (within --report-dir) selecting the canonical reports.",
    )
    parser.add_argument(
        "--include-prefix",
        default="webarena_p0_",
        help="Only reports whose file name starts with this prefix are used.",
    )
    parser.add_argument(
        "--only-round",
        action="append",
        default=[],
        help="Restrict the analysis to one or more rounds (e.g. --only-round round4). Repeatable.",
    )
    parser.add_argument(
        "--only-site",
        action="append",
        default=[],
        help="Restrict the analysis to one or more sites. Repeatable.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        action="append",
        default=[],
        help=(
            "Optional raw trajectory directory scanned when no report covers it. "
            "Repeatable. Deduplicated per (env_id, seed) keeping the newest file."
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPO_ROOT / "data" / "reports" / "webarena_failure_attribution.json",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=REPO_ROOT / "WEBARENA_FAILURE_ATTRIBUTION.md",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=REPO_ROOT / "WEBARENA_FAILURE_ATTRIBUTION.html",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=8,
        help="Examples per category in the Markdown summary.",
    )
    parser.add_argument(
        "--html-limit",
        type=int,
        default=4000,
        help="Maximum episodes embedded in the HTML view.",
    )
    return parser.parse_args()


def action_type(action: str) -> str:
    return action.split("(", 1)[0].strip() or "unknown"


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:  # pragma: no cover - corrupt evidence
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from error
    return rows


def cell_label(round_name: str, site: str, mode: str, guard: str) -> str:
    return f"{round_name}/{site}/{mode}/guard_{guard}"


def parse_report_name(path: Path) -> tuple[str, str, str, str]:
    """Derive (round, site, mode, guard) from an official report file name."""
    stem = path.stem
    match = re.match(
        r"webarena_p0_(round\d+)_dev(?:_v(\d+))?_([a-z]+)_(reactive|world-model)$", stem
    )
    if match:
        round_name, version, site, mode = match.groups()
        label = round_name + "dev" + (f"-v{version}" if version else "")
        # Development reports carry no navigation-guard dimension.
        return label, site, mode, "off"
    match = re.match(r"webarena_r3dev(?:_v(\d+))?_([a-z]+)_(reactive|world-model)$", stem)
    if match:
        version, site, mode = match.groups()
        return f"r3dev-v{version}" if version else "r3dev", site, mode, "off"
    match = re.match(r"webarena_w1_workingset_([a-z]+)_(reactive|world-model)$", stem)
    if match:
        site, mode = match.groups()
        # The W1 working set always runs with the navigation guard on.
        return "w1-workingset", site, mode, "on"
    match = re.match(r"webarena_p0_(round\d+)_holdout_([a-z]+)_(.+?)_guard_(on|off)$", stem)
    if match:
        round_name, site, mode, guard = match.groups()
        return round_name, site, mode, guard
    match = re.match(r"webarena_p0_holdout_([a-z]+)_(reactive|world-model)_guard_(on|off)$", stem)
    if match:
        site, mode, guard = match.groups()
        return "round1", site, mode, guard
    raise ValueError(f"cannot parse report name: {path.name}")


def episodes_from_reports(report_dir: Path, pattern: str, prefix: str) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for path in sorted(report_dir.glob(pattern)):
        if path.name.startswith(".") or ".incomplete_" in path.name or "_analysis" in path.name:
            continue
        if prefix and not path.name.startswith(prefix):
            continue
        try:
            round_name, site, mode, guard = parse_report_name(path)
        except ValueError:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in (payload.get("results") or {}).get(mode) or []:
            trajectory = row.get("trajectory_path")
            if not trajectory:
                continue
            episodes.append(
                {
                    "round": round_name,
                    "site": site,
                    "mode": mode,
                    "guard": guard,
                    "cell": cell_label(round_name, site, mode, guard),
                    "source": "report",
                    "report": path.name,
                    "trajectory_path": str(trajectory),
                    "reward": float(row.get("total_reward") or 0.0),
                    "success": bool(row.get("success")),
                    "steps": int(row.get("steps") or 0),
                    "task_id": row.get("task_id"),
                    "seed": row.get("seed"),
                    "env_id": row.get("env_id"),
                    "elapsed_seconds": row.get("elapsed_seconds"),
                    "last_action_error": row.get("last_action_error") or "",
                    "uses_expected_answer": bool(row.get("uses_expected_answer")),
                    "episode_attempts": row.get("episode_attempts"),
                }
            )
    return episodes


def episodes_from_corpus(root: Path) -> list[dict[str, Any]]:
    """Scan a raw trajectory tree, keeping the newest file per (env_id, seed)."""
    newest: dict[tuple[str, str], Path] = {}
    for path in root.rglob("*.jsonl"):
        stem = path.stem
        match = re.search(r"(browsergym_webarena\.[0-9]+)_seed(\d+)", stem)
        if not match:
            continue
        key = (match.group(1), match.group(2))
        current = newest.get(key)
        if current is None or stem > current.stem:
            newest[key] = path
    episodes: list[dict[str, Any]] = []
    for (env_id, seed), path in sorted(newest.items()):
        relative = path.relative_to(root)
        parts = relative.parts
        site = next((part for part in parts if part in SITE_EXPECTATIONS), "unknown")
        mode = next((part for part in parts if part in ("reactive", "world-model")), "unknown")
        guard = "on" if any("guard_on" in part for part in parts) else "off"
        episodes.append(
            {
                "round": root.name,
                "site": site,
                "mode": mode,
                "guard": guard,
                "cell": cell_label(root.name, site, mode, guard),
                "source": "corpus",
                "report": None,
                "trajectory_path": str(path),
                "reward": None,
                "success": None,
                "steps": None,
                "task_id": env_id.rsplit(".", 1)[-1],
                "seed": seed,
                "env_id": env_id,
                "elapsed_seconds": None,
                "last_action_error": "",
                "uses_expected_answer": None,
                "episode_attempts": None,
            }
        )
    return episodes


def chosen_candidate(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    decision = row.get("decision") or {}
    action = str(row.get("action") or "")
    for candidate in decision.get("candidates") or []:
        if str(candidate.get("action") or "") == action:
            return candidate
    return None


def candidate_features(candidate: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not candidate:
        return {}
    metadata = candidate.get("metadata") or {}
    components = metadata.get("structure_components") or {}
    features = components.get("feature_values") or {}
    return features


def expected_fragments(site: str, goal: str) -> tuple[str, ...]:
    lowered = goal.lower()
    fragments: list[str] = []
    for keywords, patterns in SITE_EXPECTATIONS.get(site, []):
        if any(keyword in lowered for keyword in keywords):
            fragments.extend(patterns)
    return tuple(dict.fromkeys(fragments))


def analyse(rows: Sequence[Mapping[str, Any]], meta: Mapping[str, Any]) -> dict[str, Any]:
    steps = len(rows)
    goal = ""
    if rows:
        goal = str((rows[0].get("state") or {}).get("goal") or "")
    actions = [str(row.get("action") or "") for row in rows]
    types = [action_type(action) for action in actions]
    type_counts = Counter(types)

    urls: list[str] = []
    errors: list[str] = []
    timeouts = 0
    invalid = 0
    environment = 0
    repeats = 0
    seen_actions: Counter[str] = Counter()
    clicked_targets: Counter[str] = Counter()
    candidate_counts: list[int] = []
    zero_semantic = 0
    zero_intent = 0
    zero_role = 0
    fallback_steps = 0
    low_confidence_steps = 0
    sources: Counter[str] = Counter()
    modes_seen: Counter[str] = Counter()
    submitted = False
    submitted_text = ""
    last_targets: list[str] = []

    for row in rows:
        action = str(row.get("action") or "")
        state = row.get("state") or {}
        next_state = row.get("next_state") or {}
        urls.append(str(state.get("url") or ""))
        if next_state.get("url"):
            urls.append(str(next_state["url"]))
        error = str(next_state.get("last_action_error") or "")
        errors.append(error)
        lowered = error.lower()
        if "timeout" in lowered:
            timeouts += 1
        if any(token in lowered for token in INVALID_ERROR_TOKENS):
            invalid += 1
        if any(token in lowered for token in ENVIRONMENT_ERROR_TOKENS):
            environment += 1

        seen_actions[action] += 1
        decision = row.get("decision") or {}
        mode = str(decision.get("mode") or "")
        if mode:
            modes_seen[mode] += 1
        if decision.get("requires_reobservation"):
            fallback_steps += 1
        confidence = decision.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.5:
            low_confidence_steps += 1
        candidates = list(decision.get("candidates") or [])
        if candidates:
            candidate_counts.append(len(candidates))
        candidate = chosen_candidate(row)
        if candidate:
            sources[str(candidate.get("source") or "unknown")] += 1
            name = str(candidate.get("target_name") or "")
            if name:
                clicked_targets[name] += 1
                last_targets.append(name)
            features = candidate_features(candidate)
            if features:
                if features.get("semantic_overlap") == 0:
                    zero_semantic += 1
                if features.get("intent_compatible") == 0:
                    zero_intent += 1
                if features.get("role_compatible") == 0:
                    zero_role += 1

        if action.startswith(SUBMIT_ACTION_MARKERS):
            submitted = True
            if action.startswith("send_msg_to_user"):
                submitted_text = action[len("send_msg_to_user") :][:300]

    repeats = sum(count - 1 for count in seen_actions.values() if count > 1)
    unique_urls = len({url for url in urls if url})
    expected = expected_fragments(str(meta.get("site") or ""), goal)
    reached_expected_anywhere = (
        any(fragment in url for fragment in expected for url in urls) if expected else False
    )
    final_url = urls[-1] if urls else ""
    ended_in_expected_section = (
        any(fragment in final_url for fragment in expected) if expected else False
    )
    form_intent = any(token in goal.lower() for token in FORM_INTENT_TOKENS)
    typed_actions = type_counts.get("fill", 0) + type_counts.get("type", 0) + type_counts.get("select_option", 0)
    press_enter = sum(1 for action in actions if action.startswith("press(") and "Enter" in action)
    budget = int(meta.get("steps") or steps) if meta.get("steps") else steps

    signals: dict[str, Any] = {
        "steps": steps,
        "budget": budget,
        "unique_urls": unique_urls,
        "unique_actions": len(seen_actions),
        "repeated_steps": repeats,
        "error_steps": sum(bool(error) for error in errors),
        "timeout_steps": timeouts,
        "invalid_steps": invalid,
        "environment_steps": environment,
        "submitted": submitted,
        "submitted_text": submitted_text,
        "action_types": dict(type_counts.most_common()),
        "candidate_count_median": (
            sorted(candidate_counts)[len(candidate_counts) // 2] if candidate_counts else 0
        ),
        "steps_with_candidates": len(candidate_counts),
        "zero_semantic_steps": zero_semantic,
        "zero_intent_steps": zero_intent,
        "zero_role_steps": zero_role,
        "fallback_steps": fallback_steps,
        "low_confidence_steps": low_confidence_steps,
        "candidate_sources": dict(sources.most_common()),
        "decision_modes": dict(modes_seen.most_common()),
        "top_clicked_targets": [name for name, _ in clicked_targets.most_common(6)],
        "expected_url_fragments": list(expected),
        "reached_expected_anywhere": reached_expected_anywhere,
        "ended_in_expected_section": ended_in_expected_section,
        "form_intent": form_intent,
        "typed_action_steps": typed_actions,
        "press_enter_steps": press_enter,
        "last_url": final_url,
        "url_tail": [url for url in dict.fromkeys(urls)][-6:],
        "last_target_name": last_targets[-1] if last_targets else "",
        "goal": goal,
    }
    return signals


def classify(signals: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Assign exactly one primary category, with human-readable evidence."""
    steps = int(signals["steps"])
    reasons: list[str] = []
    if steps == 0:
        return "evaluator_environment", ["轨迹没有任何有效步骤"]

    if signals["environment_steps"] >= max(2, steps // 3):
        return "evaluator_environment", [f"{signals['environment_steps']}/{steps} 步报浏览器/网络级错误"]

    if signals["invalid_steps"] >= max(1, steps // 4):
        return "element_location", [f"{signals['invalid_steps']}/{steps} 步元素无效、缺失或已脱离页面"]

    non_invalid_errors = signals["error_steps"] - signals["invalid_steps"]
    if non_invalid_errors >= max(3, steps // 3):
        return "action_execution", [
            f"{non_invalid_errors}/{steps} 步动作执行报错，其中超时 {signals['timeout_steps']} 步"
        ]

    if signals["repeated_steps"] >= max(4, steps // 2) or (
        signals["unique_urls"] <= 2 and signals["repeated_steps"] >= 3
    ):
        return "loop_stall", [
            f"重复动作 {signals['repeated_steps']} 步，唯一 URL 数 {signals['unique_urls']}"
        ]

    final_url = signals["last_url"]
    has_expectation = bool(signals["expected_url_fragments"])

    if has_expectation and not signals["reached_expected_anywhere"]:
        detail = "提交了答案但" if signals["submitted"] else "整条轨迹"
        return "wrong_route", [
            f"{detail}从未到达目标流程页面（只在外围页面活动）",
            f"期望 URL 片段 {signals['expected_url_fragments'][:3]}",
            f"末尾 URL {final_url}",
        ]

    if (
        signals["form_intent"]
        and signals["typed_action_steps"] == 0
        and signals["press_enter_steps"] == 0
        and signals["ended_in_expected_section"]
    ):
        return "form_or_search_incomplete", [
            "轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交",
            f"动作类型分布 {signals['action_types']}",
            f"末尾 URL {final_url}",
        ]

    if not signals["submitted"] and signals["ended_in_expected_section"] and steps >= 2:
        return "missing_termination", [
            "轨迹结束在目标流程页面上，但从未显式提交答案",
            f"期望 URL 片段 {signals['expected_url_fragments'][:3]}，末尾 URL {final_url}",
        ]

    zero_intent_ratio = signals["zero_intent_steps"] / steps
    zero_semantic_ratio = signals["zero_semantic_steps"] / steps
    if zero_intent_ratio >= 0.5 or zero_semantic_ratio >= 0.5:
        return "candidate_missing", [
            f"{signals['zero_intent_steps']}/{steps} 步所选动作与当前子目标意图不兼容，"
            f"{signals['zero_semantic_steps']}/{steps} 步语义重叠为 0",
            f"候选来源分布 {signals['candidate_sources']}",
            f"高频点击目标 {signals['top_clicked_targets'][:4]}",
        ]

    if not signals["submitted"] and steps >= int(signals["budget"]):
        return "budget_exhausted", [
            f"达到 {steps} 步预算且从未提交答案",
            f"高频点击目标 {signals['top_clicked_targets'][:4]}",
        ]

    reasons.append("动作可执行但未形成满足任务的完整操作序列")
    if signals["zero_intent_steps"]:
        reasons.append(f"{signals['zero_intent_steps']}/{steps} 步意图不兼容")
    if signals["top_clicked_targets"]:
        reasons.append(f"高频点击目标 {signals['top_clicked_targets'][:4]}")
    if not signals["submitted"]:
        reasons.append("未提交答案")
    return "task_understanding", reasons


def collect(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    episodes = episodes_from_reports(args.report_dir, args.report_glob, args.include_prefix)
    notes: list[str] = []
    if args.only_round:
        wanted = {value.lower() for value in args.only_round}
        episodes = [episode for episode in episodes if episode["round"].lower() in wanted]
    if args.only_site:
        wanted_sites = {value.lower() for value in args.only_site}
        episodes = [episode for episode in episodes if episode["site"].lower() in wanted_sites]
    covered = {
        (episode["site"], episode["mode"], episode["guard"], str(episode.get("task_id")), str(episode.get("seed")))
        for episode in episodes
    }
    for corpus in args.corpus_dir:
        extra = episodes_from_corpus(corpus)
        kept = []
        for episode in extra:
            key = (
                episode["site"],
                episode["mode"],
                episode["guard"],
                str(episode.get("task_id")),
                str(episode.get("seed")),
            )
            if key in covered:
                continue
            kept.append(episode)
        notes.append(f"{corpus}: {len(extra)} episodes scanned, {len(kept)} kept after report coverage")
        episodes.extend(kept)
    return episodes, notes


def build_records(episodes: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    for episode in episodes:
        path = Path(episode["trajectory_path"])
        if not path.exists():
            problems.append(f"missing trajectory: {path}")
            continue
        try:
            rows = load_rows(path)
        except ValueError as error:
            problems.append(str(error))
            continue
        signals = analyse(rows, {**episode, "steps": episode.get("steps")})
        success = episode.get("success")
        if success is None:
            success = any(float(row.get("reward") or 0.0) > 0 for row in rows)
        category, reasons = ("success", ["任务成功"]) if success else classify(signals)
        records.append(
            {
                **episode,
                "success": bool(success),
                "category": category,
                "reasons": reasons,
                "signals": signals,
            }
        )
    return records, problems


def summarise(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    categories: Counter[str] = Counter()
    by_cell: dict[str, Counter[str]] = defaultdict(Counter)
    by_site: dict[str, Counter[str]] = defaultdict(Counter)
    by_round: dict[str, Counter[str]] = defaultdict(Counter)
    success_by_cell: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
    module_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    targets_by_site: dict[str, Counter[str]] = defaultdict(Counter)
    overlap: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        category = str(record["category"])
        categories[category] += 1
        by_cell[str(record["cell"])][category] += 1
        by_site[str(record["site"])][category] += 1
        by_round[str(record["round"])][category] += 1
        success_by_cell[str(record["cell"])]["total"] += 1
        if record["success"]:
            success_by_cell[str(record["cell"])]["success"] += 1
        else:
            module_counts[CATEGORIES.get(category, {}).get("module", "unknown")] += 1
            signals = record["signals"]
            steps = max(1, int(signals["steps"]))
            # Secondary tags describe *why* the blocking symptom appeared, so a
            # stall caused by meaningless candidates is distinguishable from a
            # stall caused by an unresponsive page.
            if (
                signals["zero_intent_steps"] / steps >= 0.5
                or signals["zero_semantic_steps"] / steps >= 0.5
            ):
                overlap[category]["candidate_mismatch"] += 1
            if signals["repeated_steps"] >= 4:
                overlap[category]["repeated_actions"] += 1
            if signals["form_intent"] and signals["typed_action_steps"] == 0:
                overlap[category]["no_typing"] += 1
            if signals["error_steps"]:
                overlap[category]["action_errors"] += 1
            overlap[category]["total"] += 1
            for name in (record["signals"].get("top_clicked_targets") or [])[:3]:
                target_counts[str(name)] += 1
            for name in (record["signals"].get("top_clicked_targets") or [])[:3]:
                targets_by_site[str(record["site"])][str(name)] += 1
    return {
        "episodes": len(records),
        "failures": sum(1 for record in records if not record["success"]),
        "categories": dict(categories.most_common()),
        "module_workload": dict(module_counts.most_common()),
        "by_cell": {cell: dict(counter) for cell, counter in sorted(by_cell.items())},
        "by_site": {site: dict(counter) for site, counter in sorted(by_site.items())},
        "by_round": {name: dict(counter) for name, counter in sorted(by_round.items())},
        "success_by_cell": dict(sorted(success_by_cell.items())),
        "secondary_tags": {key: dict(counter) for key, counter in sorted(overlap.items())},
        "clicked_target_frequency_in_failures": dict(target_counts.most_common(25)),
        "clicked_target_frequency_by_site": {
            site: dict(counter.most_common(12)) for site, counter in sorted(targets_by_site.items())
        },
    }


def write_markdown(
    path: Path,
    summary: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    max_examples: int,
) -> None:
    lines: list[str] = []
    lines.append("# WebArena 失败归因（动作级）")
    lines.append("")
    lines.append(f"生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(
        f"覆盖 episode {summary['episodes']} 条，其中失败 {summary['failures']} 条。"
        "分类由可观测轨迹字段推导：执行动作、decision 候选元数据、动作错误、访问 URL、是否提交答案。"
    )
    lines.append("")
    lines.append("复现（在 WSL 中，轨迹与报告位于评测仓库）：")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/attribute_webarena_failures.py \\")
    lines.append("  --report-dir data/reports \\")
    lines.append("  --output-json data/reports/webarena_failure_attribution.json \\")
    lines.append("  --output-markdown WEBARENA_FAILURE_ATTRIBUTION.md \\")
    lines.append("  --output-html WEBARENA_FAILURE_ATTRIBUTION.html")
    lines.append("```")
    lines.append("")
    lines.append(
        "迭代单个轮次时加 `--only-round round4`，单站点加 `--only-site gitlab`；"
        "报告尚未生成的格子可用 `--corpus-dir data/trajectories_...` 直接扫轨迹目录。"
    )
    lines.append("")
    lines.append("## 失败类型分布")
    lines.append("")
    lines.append("| 类型 | 说明 | 归属模块 | 数量 | 占比 |")
    lines.append("|---|---|---|---:|---:|")
    total_failures = max(1, int(summary["failures"]))
    for category, count in summary["categories"].items():
        if category == "success":
            continue
        info = CATEGORIES.get(category, {"label": category, "module": "-"})
        lines.append(
            f"| `{category}` | {info['label']} | {info['module']} | {count} | {count / total_failures:.1%} |"
        )
    lines.append("")
    lines.append("## 模块工作量排序（按失败条数）")
    lines.append("")
    lines.append("| 模块 | 失败条数 |")
    lines.append("|---|---:|")
    for module, count in summary["module_workload"].items():
        lines.append(f"| {module} | {count} |")
    lines.append("")
    lines.append("## 各单元格成功率")
    lines.append("")
    lines.append("| 单元格 | 成功/总数 | 成功率 |")
    lines.append("|---|---:|---:|")
    for cell, stats in summary["success_by_cell"].items():
        total = max(1, stats["total"])
        lines.append(f"| {cell} | {stats['success']}/{stats['total']} | {stats['success'] / total:.1%} |")
    lines.append("")

    def distribution_table(title: str, buckets: Mapping[str, Mapping[str, int]]) -> None:
        categories = [category for category in CATEGORY_ORDER]
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| 分组 | " + " | ".join(CATEGORIES[category]["label"] for category in categories) + " | 失败合计 |")
        lines.append("|---" * (len(categories) + 2) + "|")
        for bucket, counts in buckets.items():
            row = [bucket]
            total = 0
            for category in categories:
                value = int(counts.get(category, 0))
                total += value
                row.append(str(value))
            row.append(str(total))
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    distribution_table("分站点失败类型分布", summary["by_site"])
    distribution_table("分轮次失败类型分布", summary["by_round"])

    lines.append("## 主类型 × 次级信号重叠")
    lines.append("")
    lines.append(
        "分类给每条失败 episode 一个**主类型**（阻塞症状），这里再看它同时具备哪些次级信号，"
        "用来区分「症状」和「根因」：例如 `loop_stall` 里有多大比例其实是在反复点击语义无关的控件。"
    )
    lines.append("")
    lines.append("| 主类型 | 失败条数 | 候选语义失配 | 存在重复动作 | 目标需要输入但从未输入 | 有动作报错 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for category in CATEGORY_ORDER:
        stats = summary["secondary_tags"].get(category)
        if not stats:
            continue
        total = max(1, stats["total"])
        lines.append(
            f"| {CATEGORIES[category]['label']} (`{category}`) | {stats['total']} | "
            f"{stats.get('candidate_mismatch', 0)} ({stats.get('candidate_mismatch', 0) / total:.0%}) | "
            f"{stats.get('repeated_actions', 0)} ({stats.get('repeated_actions', 0) / total:.0%}) | "
            f"{stats.get('no_typing', 0)} ({stats.get('no_typing', 0) / total:.0%}) | "
            f"{stats.get('action_errors', 0)} ({stats.get('action_errors', 0) / total:.0%}) |"
        )
    lines.append("")
    lines.append("## 失败时高频点击的元素（每条约取前 3 个高频目标统计）")
    lines.append("")
    lines.append("用于判断候选集合是否把无关控件排到了前面：")
    lines.append("")
    for name, count in summary["clicked_target_frequency_in_failures"].items():
        lines.append(f"- `{name}` × {count}")
    lines.append("")
    lines.append("### 分站点高频误点元素")
    lines.append("")
    for site, counts in summary["clicked_target_frequency_by_site"].items():
        rendered = "、".join(f"`{name}`×{count}" for name, count in counts.items())
        lines.append(f"- **{site}**：{rendered}")
    lines.append("")

    for category in CATEGORY_ORDER:
        examples = [record for record in records if record["category"] == category]
        if not examples:
            continue
        info = CATEGORIES[category]
        lines.append(f"## {info['label']}（`{category}`，{len(examples)} 条）")
        lines.append("")
        lines.append(f"归属模块：{info['module']}")
        lines.append("")
        for record in examples[:max_examples]:
            signals = record["signals"]
            lines.append(
                f"- **{record['cell']} · {record.get('env_id')} · seed {record.get('seed')}** "
                f"（{signals['steps']} 步，唯一 URL {signals['unique_urls']}）"
            )
            lines.append(f"  - 目标：{signals['goal']}")
            for reason in record["reasons"]:
                lines.append(f"  - 证据：{reason}")
            lines.append(f"  - 动作类型：{signals['action_types']}")
            if signals["top_clicked_targets"]:
                lines.append(f"  - 高频点击：{signals['top_clicked_targets']}")
            lines.append(f"  - 轨迹：{record['trajectory_path']}")
        lines.append("")

    lines.append("## 使用说明与局限")
    lines.append("")
    lines.append(
        "- 主类型是「阻塞症状 + 归属模块」，不是根因判定；判断优先级时结合上面的次级信号重叠表。"
    )
    lines.append(
        "- 期望 URL 片段表 `SITE_EXPECTATIONS` 是人工维护的启发式规则，"
        "新增站点或新流程时补充对应措辞即可，不需要改分类逻辑。"
    )
    lines.append(
        "- 分类只读取轨迹里的可观测字段（动作、decision 候选元数据、动作错误、URL、是否提交答案），"
        "不读取页面正文，也不做官方评测。"
    )
    lines.append(
        "- `budget_exhausted` 是兜底类：动作本身看起来合理、没有明显循环或走错流程，"
        "但 12 步预算内没有形成完整操作序列。"
    )
    lines.append(
        "- 建议工作流：每次改动策略后用 `--only-round round4` 重跑同一套报告，"
        "比较各类型条数与成功率的迁移；某个类型降到接近 0，说明对应模块修好了。"
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>WebArena 失败归因（动作级）</title>
<style>
 body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 0; background: #f6f8fa; color: #102a43; }
 header { background: #102a43; color: #fff; padding: 16px 24px; }
 header h1 { margin: 0 0 6px; font-size: 18px; }
 header p { margin: 0; font-size: 13px; opacity: .85; }
 .controls { padding: 12px 24px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; background: #fff; border-bottom: 1px solid #d9e2ec; position: sticky; top: 0; }
 select, input { padding: 5px 8px; border: 1px solid #bcccdc; border-radius: 4px; font-size: 13px; }
 .stats { padding: 12px 24px; font-size: 13px; color: #486581; }
 table { border-collapse: collapse; width: calc(100% - 48px); margin: 0 24px 32px; background: #fff; font-size: 13px; }
 th, td { border: 1px solid #e1e8f0; padding: 6px 8px; text-align: left; vertical-align: top; }
 th { background: #eaf3fa; position: sticky; top: 61px; }
 tr.fail td { background: #fff; }
 .cat { font-weight: 600; white-space: nowrap; }
 .cat-loop_stall { color: #b7791f; }
 .cat-element_location { color: #c0564a; }
 .cat-action_execution { color: #9c4221; }
 .cat-missing_termination { color: #2f855a; }
 .cat-form_or_search_incomplete { color: #1f6fae; }
 .cat-wrong_route { color: #6b46c1; }
 .cat-candidate_missing { color: #c53030; }
 .cat-budget_exhausted { color: #4a5568; }
 .cat-task_understanding { color: #2c5282; }
 .cat-evaluator_environment { color: #718096; }
 .cat-success { color: #2f855a; }
 details summary { cursor: pointer; color: #1f6fae; }
 .mono { font-family: Consolas, Menlo, monospace; font-size: 12px; word-break: break-all; }
</style>
</head>
<body>
<header>
  <h1>WebArena 失败归因（动作级）</h1>
  <p>__GENERATED__ · 共 __COUNT__ 条 episode（失败 __FAIL__ 条）。分类完全由轨迹可观测字段推导。</p>
</header>
<div class="controls">
  <label>轮次 <select id="round"><option value="">全部</option></select></label>
  <label>站点 <select id="site"><option value="">全部</option></select></label>
  <label>单元格 <select id="cell"><option value="">全部</option></select></label>
  <label>类型 <select id="category"><option value="">全部</option></select></label>
  <label>搜索 <input id="search" type="search" placeholder="目标 / 元素名 / URL"></label>
  <label>仅失败 <input id="failonly" type="checkbox" checked></label>
  <span id="shown"></span>
</div>
<div class="stats" id="stats"></div>
<table>
  <thead>
    <tr><th>类型</th><th>单元格</th><th>任务</th><th>步数</th><th>目标</th><th>证据</th><th>轨迹</th></tr>
  </thead>
  <tbody id="rows"></tbody>
</table>
<script>
const DATA = __DATA__;
const CATS = __CATS__;
function fill(id, values) {
  const select = document.getElementById(id);
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value; option.textContent = value; select.appendChild(option);
  }
}
fill("round", [...new Set(DATA.map(r => r.round))].sort());
fill("site", [...new Set(DATA.map(r => r.site))].sort());
fill("cell", [...new Set(DATA.map(r => r.cell))].sort());
fill("category", [...new Set(DATA.map(r => r.category))].sort());
const state = {};
for (const id of ["round", "site", "cell", "category"]) {
  state[id] = document.getElementById(id);
  state[id].addEventListener("change", render);
}
document.getElementById("search").addEventListener("input", render);
document.getElementById("failonly").addEventListener("change", render);

function render() {
  const search = document.getElementById("search").value.toLowerCase();
  const failOnly = document.getElementById("failonly").checked;
  const kept = DATA.filter(record => {
    if (state.round.value && record.round !== state.round.value) return false;
    if (state.site.value && record.site !== state.site.value) return false;
    if (state.cell.value && record.cell !== state.cell.value) return false;
    if (state.category.value && record.category !== state.category.value) return false;
    if (failOnly && record.success) return false;
    if (search) {
      const haystack = [record.goal, record.targets, record.last_url, record.category].join(" ").toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
  const counts = {};
  for (const record of kept) counts[record.category] = (counts[record.category] || 0) + 1;
  document.getElementById("stats").textContent = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([key, value]) => (CATS[key] ? CATS[key].label : key) + " " + value)
    .join(" · ");
  document.getElementById("shown").textContent = "显示 " + kept.length + " / " + DATA.length;
  const body = document.getElementById("rows");
  body.innerHTML = "";
  for (const record of kept.slice(0, 1500)) {
    const tr = document.createElement("tr");
    tr.className = record.success ? "" : "fail";
    const label = CATS[record.category] ? CATS[record.category].label : record.category;
    tr.innerHTML = "<td class='cat cat-" + record.category + "'>" + label + "</td>" +
      "<td>" + record.cell + "</td>" +
      "<td>" + (record.env_id || "") + "<br>seed " + (record.seed ?? "") + "</td>" +
      "<td>" + record.steps + "</td>" +
      "<td>" + record.goal + "</td>" +
      "<td>" + record.reasons.map(r => "• " + r).join("<br>") +
        (record.targets ? "<br>点击: " + record.targets : "") + "</td>" +
      "<td><details><summary>路径</summary><div class='mono'>" + record.trajectory_path + "</div></details></td>";
    body.appendChild(tr);
  }
}
render();
</script>
</body>
</html>
"""


def write_html(path: Path, summary: Mapping[str, Any], records: Sequence[Mapping[str, Any]], limit: int) -> None:
    payload = []
    for record in records[:limit]:
        signals = record["signals"]
        payload.append(
            {
                "round": record["round"],
                "site": record["site"],
                "cell": record["cell"],
                "category": record["category"],
                "success": bool(record["success"]),
                "env_id": record.get("env_id"),
                "seed": record.get("seed"),
                "steps": signals["steps"],
                "goal": signals["goal"],
                "reasons": record["reasons"],
                "targets": ", ".join(signals["top_clicked_targets"][:4]),
                "last_url": signals["last_url"],
                "trajectory_path": record["trajectory_path"],
            }
        )
    categories = {
        key: {"label": value["label"], "module": value["module"]} for key, value in CATEGORIES.items()
    }
    categories["success"] = {"label": "成功", "module": "-"}
    html = (
        HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
        .replace("__CATS__", json.dumps(categories, ensure_ascii=False))
        .replace("__GENERATED__", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        .replace("__COUNT__", str(summary["episodes"]))
        .replace("__FAIL__", str(summary["failures"]))
    )
    path.write_text(html, encoding="utf-8")


def main() -> int:
    args = parse_args()
    episodes, notes = collect(args)
    records, problems = build_records(episodes)
    summary = summarise(records)
    summary["notes"] = notes
    summary["problems"] = problems[:50]
    summary["categories_meta"] = CATEGORIES
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps({"summary": summary, "episodes": records}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    write_markdown(args.output_markdown, summary, records, args.max_examples)
    write_html(args.output_html, summary, records, args.html_limit)
    print(json.dumps({key: summary[key] for key in ("episodes", "failures", "categories", "module_workload")}, ensure_ascii=False, indent=1))
    for note in notes:
        print("note:", note)
    for problem in problems[:10]:
        print("problem:", problem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
