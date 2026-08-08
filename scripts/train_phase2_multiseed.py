#!/usr/bin/env python3
"""Train multiple proposal-aligned W0 variants and build a calibrated ensemble."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from torch.utils.data import DataLoader  # noqa: E402

from agent_world_model.phase2_ensemble import (  # noqa: E402
    ActionConditionedWorldModelEnsemble,
    fit_ensemble_temperatures,
    load_world_model,
)
from agent_world_model.phase2_losses import LossWeights  # noqa: E402
from agent_world_model.phase2_metrics import evaluate_thresholds  # noqa: E402
from agent_world_model.phase2_training import (  # noqa: E402
    Phase2TensorDataset,
    TrainingConfig,
    evaluate_model,
    load_jsonl,
    resolve_device,
    train_world_model,
)
from agent_world_model.world_model import WorldModelConfig  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase2_world_model_multiseed.json",
    )
    parser.add_argument("--device", default="auto")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def selection_score(metrics: Mapping[str, Any], weights: Mapping[str, float]) -> float:
    regression_penalty = float(metrics["progress"]["mae"]) + float(metrics["reward"]["mae"])
    return (
        float(weights["state_delta_f1"]) * float(metrics["state_delta"]["macro_f1_supported"])
        + float(weights["task_signal_f1"]) * float(metrics["task_signal"]["macro_f1_supported"])
        + float(weights["risk_f1"]) * float(metrics["risk"]["macro_f1_supported"])
        + float(weights["latent_cosine"]) * float(metrics["latent"]["cosine_similarity"])
        - float(weights["risk_ece_penalty"]) * float(metrics["risk"]["macro_ece"])
        - float(weights["regression_mae_penalty"]) * regression_penalty
    )


def compact_metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
    return {
        "state_delta_f1": float(metrics["state_delta"]["macro_f1_supported"]),
        "task_signal_f1": float(metrics["task_signal"]["macro_f1_supported"]),
        "risk_f1": float(metrics["risk"]["macro_f1_supported"]),
        "risk_auroc": float(metrics["risk"]["macro_auroc_supported"]),
        "risk_ece": float(metrics["risk"]["macro_ece"]),
        "risk_brier": float(metrics["risk"]["macro_brier"]),
        "risk_nll": float(metrics["risk"]["macro_nll"]),
        "risk_aurc": float(metrics["risk"]["macro_aurc"]),
        "latent_cosine": float(metrics["latent"]["cosine_similarity"]),
        "progress_mae": float(metrics["progress"]["mae"]),
        "reward_mae": float(metrics["reward"]["mae"]),
    }


def aggregate_runs(rows: list[Mapping[str, Any]], section: str) -> dict[str, dict[str, float]]:
    keys = list(rows[0][section])
    return {
        key: {
            "mean": float(statistics.fmean(float(row[section][key]) for row in rows)),
            "std": float(statistics.pstdev(float(row[section][key]) for row in rows)),
            "minimum": min(float(row[section][key]) for row in rows),
            "maximum": max(float(row[section][key]) for row in rows),
        }
        for key in keys
    }


def write_report(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    experiment_config = json.loads(args.config.read_text(encoding="utf-8"))
    base = json.loads(project_path(experiment_config["base_config"]).read_text(encoding="utf-8"))
    experiment = experiment_config["experiment"]
    outputs = experiment_config["outputs"]
    data_dir = project_path(base["data"]["directory"])
    card = json.loads((data_dir / "dataset_card.json").read_text(encoding="utf-8"))
    if not card["quality_gates"].get("p1_3000_transitions", False):
        raise RuntimeError("multi-seed formal training requires the P1 3000-transition gate")

    train_records = load_jsonl(data_dir / "train.jsonl")
    validation_records = load_jsonl(data_dir / "validation.jsonl")
    test_records = load_jsonl(data_dir / "test.jsonl")
    device = resolve_device(args.device)
    batch_size = int(base["training"]["batch_size"])
    validation_loader = DataLoader(Phase2TensorDataset(validation_records), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(Phase2TensorDataset(test_records), batch_size=batch_size, shuffle=False)
    run_directory = project_path(outputs["run_directory"])
    report_directory = project_path(outputs["report_directory"])
    run_directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    for run in experiment["runs"]:
        tag = str(run["tag"])
        seed = int(run["seed"])
        model_data = dict(base["model"])
        model_data.update(run.get("model", {}))
        training_data = dict(base["training"])
        training_data.update(run.get("training", {}))
        training_data.update({"seed": seed, "device": str(device)})
        loss_data = dict(base.get("loss_weights", {}))
        loss_data.update(run.get("loss_weights", {}))
        checkpoint = run_directory / f"world_model_{tag}_seed{seed}.pt"
        training_report = report_directory / f"training_{tag}_seed{seed}.json"
        train_report = train_world_model(
            train_records,
            validation_records,
            model_config=WorldModelConfig(**model_data),
            training_config=TrainingConfig(**training_data),
            checkpoint_path=checkpoint,
            report_path=training_report,
            loss_weights=LossWeights(**loss_data),
        )
        model = load_world_model(checkpoint, device)
        validation = evaluate_model(model, validation_loader, device=device)
        test = evaluate_model(model, test_loader, device=device)
        score = selection_score(validation, experiment["selection_weights"])
        runs.append(
            {
                "tag": tag,
                "seed": seed,
                "checkpoint": str(checkpoint.relative_to(PROJECT_ROOT)),
                "training_report": str(training_report.relative_to(PROJECT_ROOT)),
                "best_epoch": int(train_report["best_epoch"]),
                "selection_score": score,
                "validation": compact_metrics(validation),
                "test": compact_metrics(test),
            }
        )
        print(f"completed tag={tag} seed={seed} validation_score={score:.6f}", flush=True)

    ranked = sorted(runs, key=lambda item: item["selection_score"], reverse=True)
    ensemble_size = int(experiment["ensemble_size"])
    selected = ranked[:ensemble_size]
    selected_models = [load_world_model(project_path(row["checkpoint"]), device) for row in selected]
    temperatures = fit_ensemble_temperatures(selected_models, validation_loader, device=device)
    uncalibrated_model = ActionConditionedWorldModelEnsemble(selected_models).to(device)
    calibrated_model = ActionConditionedWorldModelEnsemble(
        selected_models, temperatures=temperatures
    ).to(device)
    validation_uncalibrated = evaluate_model(uncalibrated_model, validation_loader, device=device)
    validation_calibrated = evaluate_model(calibrated_model, validation_loader, device=device)
    test_calibrated = evaluate_model(calibrated_model, test_loader, device=device)

    thresholds = dict(base["acceptance_thresholds"])
    thresholds.update(experiment.get("extra_acceptance_thresholds", {}))
    validation_acceptance = evaluate_thresholds(validation_calibrated, thresholds)
    test_acceptance = evaluate_thresholds(test_calibrated, thresholds)
    generated = datetime.now(timezone.utc).isoformat()
    manifest_path = project_path(outputs["ensemble_manifest"])
    manifest = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "experiment": experiment["name"],
        "selection_split": "validation",
        "members": [
            {
                "tag": row["tag"],
                "seed": row["seed"],
                "checkpoint": row["checkpoint"],
                "selection_score": row["selection_score"],
            }
            for row in selected
        ],
        "temperatures": temperatures,
        "champion_single_checkpoint": selected[0]["checkpoint"],
    }
    write_report(manifest_path, manifest)

    validation_report = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "split": "validation",
        "device": str(device),
        "ensemble_manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
        "metrics": validation_calibrated,
        "uncalibrated_metrics": validation_uncalibrated,
        "acceptance": validation_acceptance,
    }
    test_report = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "split": "test",
        "device": str(device),
        "ensemble_manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
        "metrics": test_calibrated,
        "acceptance": test_acceptance,
    }
    write_report(project_path(outputs["validation_report"]), validation_report)
    write_report(project_path(outputs["test_report"]), test_report)
    summary = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "experiment": experiment["name"],
        "device": str(device),
        "run_count": len(runs),
        "ensemble_size": ensemble_size,
        "runs": ranked,
        "run_stability": {
            "validation": aggregate_runs(runs, "validation"),
            "test": aggregate_runs(runs, "test"),
        },
        "selected_members": manifest["members"],
        "temperatures": temperatures,
        "calibration_comparison": {
            "risk_ece_before": validation_uncalibrated["risk"]["macro_ece"],
            "risk_ece_after": validation_calibrated["risk"]["macro_ece"],
            "risk_brier_before": validation_uncalibrated["risk"]["macro_brier"],
            "risk_brier_after": validation_calibrated["risk"]["macro_brier"],
        },
        "validation_acceptance": validation_acceptance,
        "test_acceptance": test_acceptance,
        "ensemble_validation": compact_metrics(validation_calibrated),
        "ensemble_test": compact_metrics(test_calibrated),
    }
    write_report(project_path(outputs["summary_report"]), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if validation_acceptance["passed"] and test_acceptance["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
