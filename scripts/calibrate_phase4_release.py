#!/usr/bin/env python3
"""Select the largest validation-safe W4/W3 checkpoint blend, then test once."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from agent_world_model.phase2_ensemble import (  # noqa: E402
    ActionConditionedWorldModelEnsemble,
    fit_ensemble_temperatures,
    load_world_model,
)
from agent_world_model.phase2_training import (  # noqa: E402
    Phase2TensorDataset,
    load_jsonl,
    resolve_device,
)
from run_phase4_feedback import compact, evaluate_ensemble  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=PROJECT_ROOT / "configs" / "phase4_feedback.json"
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def checks(
    candidate: dict[str, float],
    baseline: dict[str, float],
    release: dict[str, float],
) -> dict[str, bool]:
    return {
        "validation_pairwise_not_below_w3": candidate["pairwise_accuracy"]
        >= baseline["pairwise_accuracy"] - float(release["pairwise_accuracy_tolerance"]),
        "validation_regret_not_above_w3": candidate["mean_decision_regret"]
        <= baseline["mean_decision_regret"] + float(release["decision_regret_tolerance"]),
        "validation_latent_mse_not_regressed": candidate["latent_mse"]
        <= baseline["latent_mse"] * (1.0 + float(release["latent_mse_relative_tolerance"])),
        "validation_risk_ece_not_regressed": candidate["risk_ece"]
        <= baseline["risk_ece"] + float(release["risk_ece_absolute_tolerance"]),
    }


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    report_path = args.report or project_path(config["outputs"]["report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    baseline_manifest_path = project_path(config["baseline_ensemble"])
    baseline_manifest = json.loads(baseline_manifest_path.read_text(encoding="utf-8"))
    priority = next(row for row in report["variants"] if row["name"] == "priority")
    priority_manifest_path = project_path(priority["manifest"])
    priority_manifest = json.loads(priority_manifest_path.read_text(encoding="utf-8"))
    device = resolve_device(args.device)

    baseline_models = [
        load_world_model(project_path(member["checkpoint"]), device)
        for member in baseline_manifest["members"]
    ]
    priority_models = [
        load_world_model(project_path(member["checkpoint"]), device)
        for member in priority_manifest["members"]
    ]
    models = [*baseline_models, *priority_models]
    data_dir = project_path(config["data"]["directory"])
    validation_records = load_jsonl(data_dir / "validation.jsonl")
    test_records = load_jsonl(data_dir / "test.jsonl")
    batch_size = int(config["training"]["batch_size"])
    loader = DataLoader(
        Phase2TensorDataset(validation_records), batch_size=batch_size, shuffle=False
    )
    baseline_weights = [float(value) for value in baseline_manifest["member_weights"]]
    priority_weights = [float(value) for value in priority_manifest["member_weights"]]
    baseline_summary = report["baseline_w3"]["validation"]
    release = config["release"]
    candidates: list[dict[str, object]] = []

    # Validation-only release selection. Prefer the largest W4 contribution
    # that passes every non-regression gate; test remains untouched until then.
    for step in range(10, -1, -1):
        w4_fraction = step / 10.0
        weights = [
            *((1.0 - w4_fraction) * value for value in baseline_weights),
            *(w4_fraction * value for value in priority_weights),
        ]
        ensemble_uncalibrated = ActionConditionedWorldModelEnsemble(
            models, member_weights=weights
        ).to(device)
        temperatures = fit_ensemble_temperatures(
            list(ensemble_uncalibrated.models), loader, device=device
        )
        ensemble = ActionConditionedWorldModelEnsemble(
            models, member_weights=weights, temperatures=temperatures
        ).to(device)
        ensemble.eval()
        metrics = compact(
            evaluate_ensemble(
                ensemble,
                validation_records,
                device=device,
                batch_size=batch_size,
            )
        )
        row_checks = checks(metrics, baseline_summary, release)
        candidates.append(
            {
                "w4_fraction": w4_fraction,
                "member_weights": weights,
                "temperatures": temperatures,
                "validation": metrics,
                "checks": row_checks,
                "passed": all(row_checks.values()),
            }
        )
        print(
            f"w4_fraction={w4_fraction:.1f} passed={all(row_checks.values())} "
            f"mse={metrics['latent_mse']:.6f} acc={metrics['pairwise_accuracy']:.4f}",
            flush=True,
        )

    selected = next((row for row in candidates if row["passed"]), None)
    if selected is None:
        raise RuntimeError("no W4/W3 validation-safe release blend exists")
    selected_weights = [float(value) for value in selected["member_weights"]]
    selected_ensemble = ActionConditionedWorldModelEnsemble(
        models,
        member_weights=selected_weights,
        temperatures=selected["temperatures"],
    ).to(device)
    selected_ensemble.eval()
    test = compact(
        evaluate_ensemble(
            selected_ensemble, test_records, device=device, batch_size=batch_size
        )
    )
    manifest = {
        "schema_version": 1,
        "phase": 4,
        "variant": "priority_conservative_release",
        "selection_split": "validation",
        "w4_fraction": selected["w4_fraction"],
        "members": [
            *[
                {"source": "w3", "seed": row["seed"], "checkpoint": row["checkpoint"]}
                for row in baseline_manifest["members"]
            ],
            *[
                {"source": "w4_priority", "seed": row["seed"], "checkpoint": row["checkpoint"]}
                for row in priority_manifest["members"]
            ],
        ],
        "member_weights": selected_weights,
        "temperatures": selected["temperatures"],
    }
    output = project_path(config["outputs"]["selected_manifest"])
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["released_w4"] = {
        "selected_on": "validation",
        "selection_rule": "largest W4 fraction satisfying prediction, ranking, regret, and calibration non-regression gates",
        "w4_fraction": selected["w4_fraction"],
        "manifest": str(output.relative_to(PROJECT_ROOT)),
        "validation": selected["validation"],
        "test": test,
        "release": {"passed": True, "checks": selected["checks"]},
        "candidate_trace": candidates,
    }
    report["release"] = report["released_w4"]["release"]
    report["release"]["policy"] = report["released_w4"]["selection_rule"]
    report["release"]["calibrated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["released_w4"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
