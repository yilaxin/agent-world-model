#!/usr/bin/env python3
"""Build the phase-four feedback pool and run equal-budget replay ablations."""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402
from torch.nn import functional as F  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from agent_world_model.phase2_ensemble import (  # noqa: E402
    ActionConditionedWorldModelEnsemble,
    EnsembleWorldModelPredictor,
    fit_ensemble_rank_weights,
    fit_ensemble_temperatures,
    load_world_model,
)
from agent_world_model.phase2_losses import LossWeights  # noqa: E402
from agent_world_model.phase2_schema import (  # noqa: E402
    RISK_LABELS,
    STATE_DELTA_LABELS,
    encode_action,
)
from agent_world_model.phase2_training import (  # noqa: E402
    Phase2TensorDataset,
    TrainingConfig,
    evaluate_model,
    load_jsonl,
    predicted_action_score,
    resolve_device,
    train_world_model,
)
from agent_world_model.phase4_feedback import (  # noqa: E402
    FeedbackPriorityConfig,
    build_replay_view,
    feedback_components,
    feedback_summary,
    pairwise_decision_metrics,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase4_feedback.json",
    )
    parser.add_argument("--device")
    parser.add_argument("--variant", action="append", default=[])
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _symexp(value: torch.Tensor) -> torch.Tensor:
    return torch.sign(value) * torch.expm1(value.abs())


@torch.no_grad()
def score_and_error(
    predictor: EnsembleWorldModelPredictor,
    records: Sequence[Mapping[str, Any]],
    *,
    batch_size: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute W3 predicted utility and multi-head prediction-to-reality error."""

    scores: dict[str, float] = {}
    errors: dict[str, float] = {}
    model = predictor.model
    device = predictor.device
    for start in range(0, len(records), batch_size):
        rows = records[start : start + batch_size]
        state = torch.tensor(
            [row["state_vector"] for row in rows], dtype=torch.float32, device=device
        )
        action = torch.tensor(
            [encode_action(str(row["action"]), model.config.action_dim)[0] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        target_state = torch.tensor(
            [row["next_state_vector"] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        outputs = model(state, action, next_state=target_state)
        score = predicted_action_score(outputs)
        state_error = F.mse_loss(
            outputs["predicted_next_state"], target_state, reduction="none"
        ).mean(dim=-1)
        state_delta = torch.tensor(
            [
                [row["state_delta"][name] for name in STATE_DELTA_LABELS]
                for row in rows
            ],
            dtype=torch.float32,
            device=device,
        )
        task_signal = torch.tensor(
            [
                [row["task_signals"]["invalid_action"], row["task_signals"]["terminal"]]
                for row in rows
            ],
            dtype=torch.float32,
            device=device,
        )
        risk = torch.tensor(
            [[row["risks"][name] for name in RISK_LABELS] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        classification_error = (
            F.binary_cross_entropy_with_logits(
                outputs["state_delta_logits"], state_delta, reduction="none"
            ).mean(dim=-1)
            + F.binary_cross_entropy_with_logits(
                outputs["task_signal_logits"], task_signal, reduction="none"
            ).mean(dim=-1)
            + F.binary_cross_entropy_with_logits(
                outputs["risk_logits"], risk, reduction="none"
            ).mean(dim=-1)
        ) / 3.0
        progress = torch.tensor(
            [row["task_signals"]["progress"] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        reward = torch.tensor(
            [row["task_signals"]["reward"] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        numeric_error = 0.5 * (
            (_symexp(outputs["progress_symlog"]) - progress).abs()
            + (_symexp(outputs["reward_symlog"]) - reward).abs()
        )
        combined = state_error + classification_error + numeric_error
        for row, row_score, row_error in zip(rows, score, combined):
            key = str(row["example_id"])
            scores[key] = float(row_score)
            errors[key] = float(row_error)
    return scores, errors


def model_scores(
    model: ActionConditionedWorldModelEnsemble,
    records: Sequence[Mapping[str, Any]],
    *,
    device: torch.device,
    batch_size: int,
) -> dict[str, float]:
    result: dict[str, float] = {}
    with torch.no_grad():
        for start in range(0, len(records), batch_size):
            rows = records[start : start + batch_size]
            state = torch.tensor(
                [row["state_vector"] for row in rows], dtype=torch.float32, device=device
            )
            action = torch.tensor(
                [encode_action(str(row["action"]), model.config.action_dim)[0] for row in rows],
                dtype=torch.float32,
                device=device,
            )
            values = predicted_action_score(model(state, action))
            for row, value in zip(rows, values):
                result[str(row["example_id"])] = float(value)
    return result


def evaluate_ensemble(
    model: ActionConditionedWorldModelEnsemble,
    records: Sequence[Mapping[str, Any]],
    *,
    device: torch.device,
    batch_size: int,
) -> dict[str, Any]:
    metrics = evaluate_model(
        model,
        DataLoader(Phase2TensorDataset(records), batch_size=batch_size, shuffle=False),
        device=device,
    )
    metrics["decision"] = pairwise_decision_metrics(
        records,
        model_scores(model, records, device=device, batch_size=batch_size),
    )
    return metrics


def compact(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "latent_mse": metrics["latent"]["mse"],
        "latent_cosine": metrics["latent"]["cosine_similarity"],
        "progress_mae": metrics["progress"]["mae"],
        "reward_mae": metrics["reward"]["mae"],
        "state_delta_f1": metrics["state_delta"]["macro_f1_supported"],
        "task_signal_f1": metrics["task_signal"]["macro_f1_supported"],
        "risk_f1": metrics["risk"]["macro_f1_supported"],
        "risk_ece": metrics["risk"]["macro_ece"],
        **metrics["decision"],
    }


def selection_key(metrics: Mapping[str, Any]) -> tuple[float, ...]:
    summary = compact(metrics)
    return (
        float(summary["pairwise_accuracy"]),
        -float(summary["mean_decision_regret"]),
        -float(summary["risk_ece"]),
        -float(summary["latent_mse"]),
    )


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.smoke:
        config["outputs"] = {
            "directory": "artifacts/phase4_smoke",
            "feedback_pool": "data/phase4/feedback_pool_smoke.jsonl",
            "report": "data/reports/phase4_feedback_experiment_smoke.json",
            "selected_manifest": "artifacts/phase4_smoke/world_model_ensemble_w4.json",
        }
    device = resolve_device(args.device or config["training"]["device"])
    data_dir = project_path(config["data"]["directory"])
    train_records = load_jsonl(data_dir / "train.jsonl")
    validation_records = load_jsonl(data_dir / "validation.jsonl")
    test_records = load_jsonl(data_dir / "test.jsonl")
    if args.smoke:
        train_records = train_records[:384]
        validation_records = validation_records[:192]
        test_records = test_records[:192]

    baseline_path = project_path(config["baseline_ensemble"])
    baseline_predictor = EnsembleWorldModelPredictor(baseline_path, device=str(device))
    batch_size = int(config["training"]["batch_size"])
    train_scores, train_errors = score_and_error(
        baseline_predictor, train_records, batch_size=batch_size
    )
    feedback = feedback_components(
        train_records,
        predicted_scores=train_scores,
        prediction_errors=train_errors,
    )
    feedback_config = FeedbackPriorityConfig(**config["feedback"])
    pool_path = project_path(config["outputs"]["feedback_pool"])
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    with pool_path.open("w", encoding="utf-8") as file:
        for row in feedback:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    baseline_models = list(baseline_predictor.model.models)
    baseline_validation = evaluate_ensemble(
        baseline_predictor.model,
        validation_records,
        device=device,
        batch_size=batch_size,
    )
    variants = [
        item
        for item in config["variants"]
        if not args.variant or item["name"] in set(args.variant)
    ]
    output_dir = project_path(config["outputs"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    initial_manifest = json.loads(baseline_path.read_text(encoding="utf-8"))
    member_specs = initial_manifest["members"]
    loss_weights = LossWeights(**config["loss_weights"])
    variant_reports: list[dict[str, Any]] = []

    for variant in variants:
        name = str(variant["name"])
        replay_records = build_replay_view(
            train_records,
            feedback,
            strategy=str(variant["strategy"]),
            config=feedback_config,
            omitted_components=variant.get("omit", []),
        )
        checkpoints: list[Path] = []
        runs: list[dict[str, Any]] = []
        for member_index, member in enumerate(member_specs):
            seed = int(member["seed"])
            initial_checkpoint = project_path(member["checkpoint"])
            checkpoint = output_dir / name / f"member_seed{seed}.pt"
            report_path = output_dir / name / f"member_seed{seed}_training.json"
            training = dict(config["training"])
            training["seed"] = seed
            if args.device:
                training["device"] = args.device
            if args.smoke:
                training.update({"epochs": 1, "patience": 1})
            training_config = TrainingConfig(**training)
            report = train_world_model(
                replay_records,
                validation_records,
                model_config=baseline_models[member_index].config,
                training_config=training_config,
                checkpoint_path=checkpoint,
                report_path=report_path,
                loss_weights=loss_weights,
                initial_checkpoint_path=initial_checkpoint,
            )
            checkpoints.append(checkpoint)
            runs.append(
                {
                    "seed": seed,
                    "initial_checkpoint": str(initial_checkpoint.relative_to(PROJECT_ROOT)),
                    "checkpoint": str(checkpoint.relative_to(PROJECT_ROOT)),
                    "best_epoch": report["best_epoch"],
                    "validation_pairwise_accuracy": report["validation"]["pairwise_ranking"]["accuracy"],
                }
            )
            print(f"variant={name} seed={seed} epoch={report['best_epoch']}", flush=True)

        models = [load_world_model(path, device) for path in checkpoints]
        validation_loader = DataLoader(
            Phase2TensorDataset(validation_records), batch_size=batch_size, shuffle=False
        )
        temperatures = fit_ensemble_temperatures(models, validation_loader, device=device)
        member_weights = fit_ensemble_rank_weights(
            models, validation_records, device=device
        )
        ensemble = ActionConditionedWorldModelEnsemble(
            models, temperatures=temperatures, member_weights=member_weights
        ).to(device)
        ensemble.eval()
        validation = evaluate_ensemble(
            ensemble, validation_records, device=device, batch_size=batch_size
        )
        manifest = {
            "schema_version": 1,
            "phase": 4,
            "variant": name,
            "selection_split": "validation",
            "members": [
                {"seed": run["seed"], "checkpoint": run["checkpoint"]}
                for run in runs
            ],
            "temperatures": temperatures,
            "member_weights": member_weights,
        }
        manifest_path = output_dir / name / "ensemble_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        variant_reports.append(
            {
                "name": name,
                "strategy": variant["strategy"],
                "omitted_components": variant.get("omit", []),
                "runs": runs,
                "manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
                "validation": compact(validation),
                "selection_key": list(selection_key(validation)),
            }
        )
        print(
            f"variant={name} validation_pairwise={validation['decision']['pairwise_accuracy']:.4f} "
            f"regret={validation['decision']['mean_decision_regret']:.4f}",
            flush=True,
        )

    priority_variants = [row for row in variant_reports if row["name"] == "priority"]
    if not priority_variants:
        raise RuntimeError("the full priority variant is required for W4 selection")
    selected = priority_variants[0]
    selected_source = project_path(selected["manifest"])
    selected_manifest = project_path(config["outputs"]["selected_manifest"])
    selected_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected_source, selected_manifest)
    final_predictor = EnsembleWorldModelPredictor(selected_manifest, device=str(device))
    final_test = evaluate_ensemble(
        final_predictor.model, test_records, device=device, batch_size=batch_size
    )
    baseline_test = evaluate_ensemble(
        baseline_predictor.model, test_records, device=device, batch_size=batch_size
    )
    base_validation = compact(baseline_validation)
    selected_validation = selected["validation"]
    release_config = config["release"]
    release_checks = {
        "validation_pairwise_not_below_w3": selected_validation["pairwise_accuracy"]
        >= base_validation["pairwise_accuracy"] - float(release_config["pairwise_accuracy_tolerance"]),
        "validation_regret_not_above_w3": selected_validation["mean_decision_regret"]
        <= base_validation["mean_decision_regret"] + float(release_config["decision_regret_tolerance"]),
        "validation_latent_mse_not_regressed": selected_validation["latent_mse"]
        <= base_validation["latent_mse"] * (1.0 + float(release_config["latent_mse_relative_tolerance"])),
        "validation_risk_ece_not_regressed": selected_validation["risk_ece"]
        <= base_validation["risk_ece"] + float(release_config["risk_ece_absolute_tolerance"]),
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 4,
        "device": str(device),
        "cuda_device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "experiment_design": {
            "selection_split": "validation",
            "test_evaluated_after_variant_selection": True,
            "equal_budget": True,
            "ensemble_member_count": len(member_specs),
            "feedback_config": feedback_config.to_dict(),
            "training_config": config["training"],
        },
        "feedback_pool": {
            "path": str(pool_path.relative_to(PROJECT_ROOT)),
            "summary": feedback_summary(feedback),
        },
        "baseline_w3": {
            "manifest": str(baseline_path.relative_to(PROJECT_ROOT)),
            "validation": base_validation,
            "test": compact(baseline_test),
        },
        "variants": variant_reports,
        "selected_w4": {
            "variant": selected["name"],
            "manifest": str(selected_manifest.relative_to(PROJECT_ROOT)),
            "validation": selected_validation,
            "test": compact(final_test),
        },
        "release": {
            "passed": all(release_checks.values()),
            "checks": release_checks,
            "policy": "W4 replaces W3 only when validation prediction, ranking, regret, and calibration do not regress.",
        },
        "interpretation_limits": [
            "Feedback labels use only environment-observed factual/counterfactual outcomes and logged task signals.",
            "All replay variants see the same records for the same number of epochs; mean-one weights change emphasis, not data or update count.",
            "This offline experiment does not substitute for the separately reported WebArena online success rate.",
        ],
    }
    report_path = project_path(config["outputs"]["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"release": report["release"], "selected_w4": report["selected_w4"]}, ensure_ascii=False, indent=2))
    return 0 if report["release"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
