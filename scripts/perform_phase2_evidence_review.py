#!/usr/bin/env python3
"""Stamp audited phase-two rows as evidence-approved without human claims."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.human_review import read_review_csv, write_review_csv  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def _path(value: Path) -> Path:
    return value if value.is_absolute() else PROJECT_ROOT / value


def main() -> int:
    args = parse_args()
    source = _path(args.reviews)
    audit_path = _path(args.audit)
    output = _path(args.output)
    report_path = _path(args.report)
    rows = read_review_csv(source)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    ready = set(audit.get("evidence_ready_example_ids", []))
    reviewed_at = datetime.now(timezone.utc).isoformat()
    changed = 0
    for row in rows:
        if row["example_id"] not in ready:
            continue
        if row["review_status"].strip().lower() not in {"", "pending", "evidence_approved"}:
            continue
        row["review_status"] = "evidence_approved"
        row["reviewer"] = "codex-evidence-review-v1"
        row["reviewed_at_utc"] = reviewed_at
        row["notes"] = (
            "Codex证据复核v1：原始记录唯一匹配、环境实测、反事实配对ID完整、"
            "终止且非成功、奖励非正、队列标签与结果派生规则一致；非人工签字。"
        )
        changed += 1
    write_review_csv(output, rows)
    report = {
        "schema_version": 1,
        "generated_at_utc": reviewed_at,
        "source_review_csv": str(source),
        "source_audit": str(audit_path),
        "output_review_csv": str(output),
        "queue_row_count": len(rows),
        "evidence_ready_count": len(ready),
        "status_updated_count": changed,
        "review_status_counts": dict(Counter(row["review_status"] for row in rows)),
        "review_method": "codex_evidence_review_v1",
        "human_signoff": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
