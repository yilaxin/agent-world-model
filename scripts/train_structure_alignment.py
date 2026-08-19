#!/usr/bin/env python3
"""Train and evaluate the proposal's task-to-GUI dynamic alignment module."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402
from torch import nn  # noqa: E402

from agent_world_model.phase2_metrics import binary_metrics  # noqa: E402
from agent_world_model.phase2_schema import encode_action  # noqa: E402
from agent_world_model.phase2_training import load_jsonl, resolve_device, seed_everything  # noqa: E402
from agent_world_model.phase3_candidates import structural_consistency  # noqa: E402
from agent_world_model.reactive_agent import ElementRef, parse_elements  # noqa: E402
from agent_world_model.structure_alignment import (  # noqa: E402
    FEATURE_NAMES,
    StructureAlignmentConfig,
    StructureAlignmentModel,
    alignment_features,
)


@dataclass(frozen=True)
class AlignmentExample:
    group_id: str
    task_id: str
    phase: str
    bid: str
    features: list[float]
    label: float
    baseline_score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase3_structure_alignment.json",
    )
    parser.add_argument("--device")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def raw_index(directories: list[Path]) -> dict[tuple[str, int, str], dict[str, Any]]:
    result: dict[tuple[str, int, str], dict[str, Any]] = {}
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.jsonl")):
            for record in load_jsonl(path):
                key = (
                    str(record.get("episode_id") or record.get("run_id") or ""),
                    int(record.get("step_index", 0) or 0),
                    str(record.get("action", "")),
                )
                result[key] = record
    return result


def action_for_element(element: ElementRef, action_type: str) -> str:
    quoted = json.dumps(element.bid)
    if action_type in {"fill", "type"}:
        return f"fill({quoted}, \"value\")"
    if action_type == "select_option":
        return f"select_option({quoted}, \"value\")"
    return f"click({quoted}, \"left\")"


def build_examples(
    records: list[dict[str, Any]],
    trajectories: Mapping[tuple[str, int, str], dict[str, Any]],
    *,
    max_negatives: int,
) -> tuple[list[AlignmentExample], dict[str, int]]:
    result: list[AlignmentExample] = []
    counters: dict[str, int] = defaultdict(int)
    for record in records:
        targets = {str(value) for value in record.get("target_element_ids", [])}
        if not targets:
            counters["no_target"] += 1
            continue
        key = (record["episode_id"], int(record["step_index"]), record["action"])
        raw = trajectories.get(key)
        if raw is None:
            counters["raw_missing"] += 1
            continue
        state = dict(raw["state"])
        axtree_value = state.get("axtree", "")
        axtree = str(axtree_value.get("text", "")) if isinstance(axtree_value, Mapping) else str(axtree_value)
        elements = parse_elements(axtree)
        visible = {element.bid for element in elements}
        if not targets & visible:
            counters["target_not_visible"] += 1
            continue
        _, parsed = encode_action(record["action"])
        action_type = parsed["action_type"]
        recent_actions = state.get("recent_actions") or state.get("history") or []
        positives = [element for element in elements if element.bid in targets]
        negatives = [element for element in elements if element.bid not in targets]
        negatives.sort(
            key=lambda element: hashlib.sha256(
                f"{record['example_id']}:{element.bid}".encode()
            ).hexdigest()
        )
        phase = "initial" if int(record["step_index"]) == 0 else "continuation"
        for element in positives + negatives[:max_negatives]:
            features, _ = alignment_features(
                record["instruction"],
                element,
                action_type,
                step_index=int(record["step_index"]),
                recent_actions=recent_actions,
            )
            baseline, _ = structural_consistency(
                record["instruction"], axtree, action_for_element(element, action_type)
            )
            result.append(
                AlignmentExample(
                    group_id=record["example_id"],
                    task_id=record["task_id"],
                    phase=phase,
                    bid=element.bid,
                    features=features,
                    label=float(element.bid in targets),
                    baseline_score=baseline,
                )
            )
        counters["groups"] += 1
        counters["positives"] += len(positives)
        counters["negatives"] += min(max_negatives, len(negatives))
    return result, dict(counters)


def ranking_metrics(examples: list[AlignmentExample], scores: list[float]) -> dict[str, Any]:
    groups: dict[str, list[tuple[AlignmentExample, float]]] = defaultdict(list)
    for example, score in zip(examples, scores):
        groups[example.group_id].append((example, score))
    reciprocal: list[float] = []
    recalls: dict[int, list[float]] = {1: [], 3: [], 5: []}
    by_phase: dict[str, list[float]] = defaultdict(list)
    for rows in groups.values():
        ordered = sorted(rows, key=lambda item: item[1], reverse=True)
        positive_ranks = [index for index, (example, _) in enumerate(ordered, start=1) if example.label >= 0.5]
        if not positive_ranks:
            continue
        best = min(positive_ranks)
        reciprocal.append(1.0 / best)
        for k in recalls:
            recalls[k].append(float(best <= k))
        by_phase[ordered[0][0].phase].append(float(best <= 1))
    classification = binary_metrics([example.label for example in examples], scores)
    top1 = statistics.fmean(recalls[1]) if recalls[1] else 0.0
    return {
        "group_count": len(reciprocal),
        "target_recall_at_1": top1,
        "target_recall_at_3": statistics.fmean(recalls[3]) if recalls[3] else 0.0,
        "target_recall_at_5": statistics.fmean(recalls[5]) if recalls[5] else 0.0,
        "mrr": statistics.fmean(reciprocal) if reciprocal else 0.0,
        "structure_mismatch_rate": 1.0 - top1,
        "top1_by_phase": {phase: statistics.fmean(values) for phase, values in sorted(by_phase.items())},
        "classification": classification,
    }


@torch.no_grad()
def model_scores(model: StructureAlignmentModel, examples: list[AlignmentExample], device: torch.device) -> list[float]:
    model.eval()
    features = torch.tensor([example.features for example in examples], dtype=torch.float32, device=device)
    return torch.sigmoid(model(features)).cpu().tolist()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    data_dir = project_path(config["data"]["dataset_directory"])
    trajectories = raw_index([project_path(path) for path in config["data"]["trajectory_directories"]])
    examples: dict[str, list[AlignmentExample]] = {}
    audits: dict[str, Any] = {}
    for split in ("train", "validation", "test"):
        examples[split], audits[split] = build_examples(
            load_jsonl(data_dir / f"{split}.jsonl"),
            trajectories,
            max_negatives=int(config["data"]["max_negatives_per_state"]),
        )
        if not examples[split]:
            raise RuntimeError(f"no alignment examples available for {split}")

    device = resolve_device(args.device or config["training"]["device"])
    run_dir = project_path(config["outputs"]["run_directory"])
    run_dir.mkdir(parents=True, exist_ok=True)
    run_reports: list[dict[str, Any]] = []
    train_x = torch.tensor([row.features for row in examples["train"]], dtype=torch.float32, device=device)
    train_y = torch.tensor([row.label for row in examples["train"]], dtype=torch.float32, device=device)
    positive = float(train_y.sum())
    pos_weight = torch.tensor((len(train_y) - positive) / max(1.0, positive), device=device)

    for seed_value in config["training"]["seeds"]:
        seed = int(seed_value)
        seed_everything(seed)
        model = StructureAlignmentModel(StructureAlignmentConfig(**config["model"])).to(device)
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=float(config["training"]["learning_rate"]),
            weight_decay=float(config["training"]["weight_decay"]),
        )
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        best_mrr = -1.0
        best_state: dict[str, torch.Tensor] | None = None
        stale = 0
        history: list[dict[str, float]] = []
        for epoch in range(1, int(config["training"]["epochs"]) + 1):
            model.train()
            permutation = torch.randperm(len(train_x), device=device)
            total_loss = 0.0
            for start in range(0, len(train_x), 256):
                indices = permutation[start : start + 256]
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(model(train_x[indices]), train_y[indices])
                loss.backward()
                optimizer.step()
                total_loss += float(loss.detach()) * len(indices)
            validation_scores = model_scores(model, examples["validation"], device)
            validation = ranking_metrics(examples["validation"], validation_scores)
            history.append({"epoch": epoch, "train_loss": total_loss / len(train_x), "validation_mrr": validation["mrr"]})
            if validation["mrr"] > best_mrr + 1e-6:
                best_mrr = float(validation["mrr"])
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
                stale = 0
            else:
                stale += 1
                if stale >= int(config["training"]["patience"]):
                    break
        assert best_state is not None
        model.load_state_dict(best_state)
        checkpoint = run_dir / f"structure_aligner_seed{seed}.pt"
        torch.save(
            {
                "schema_version": 1,
                "model_config": model.config.to_dict(),
                "model_state_dict": model.state_dict(),
                "seed": seed,
                "validation_mrr": best_mrr,
            },
            checkpoint,
        )
        validation = ranking_metrics(examples["validation"], model_scores(model, examples["validation"], device))
        test = ranking_metrics(examples["test"], model_scores(model, examples["test"], device))
        run_reports.append(
            {
                "seed": seed,
                "checkpoint": str(checkpoint.relative_to(PROJECT_ROOT)),
                "epochs_ran": len(history),
                "validation": validation,
                "test": test,
                "history": history,
            }
        )
        print(f"alignment seed={seed} validation_mrr={validation['mrr']:.4f}", flush=True)

    selected = max(run_reports, key=lambda row: row["validation"]["mrr"])
    best_checkpoint = project_path(config["outputs"]["best_checkpoint"])
    best_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_path(selected["checkpoint"]), best_checkpoint)
    baseline = {
        split: ranking_metrics(examples[split], [row.baseline_score for row in examples[split]])
        for split in ("validation", "test")
    }
    acceptance = {
        "test_target_recall_at_3": selected["test"]["target_recall_at_3"] >= 0.8,
        "test_mrr_not_below_rule_baseline": selected["test"]["mrr"] >= baseline["test"]["mrr"],
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "feature_names": list(FEATURE_NAMES),
        "data_audit": audits,
        "baseline": baseline,
        "runs": run_reports,
        "selected_seed": selected["seed"],
        "best_checkpoint": str(best_checkpoint.relative_to(PROJECT_ROOT)),
        "selected_validation": selected["validation"],
        "selected_test": selected["test"],
        "acceptance": {
            "passed": all(acceptance.values()),
            "checks": acceptance,
        },
    }
    output = project_path(config["outputs"]["report"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["acceptance"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
