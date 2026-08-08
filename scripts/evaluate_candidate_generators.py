#!/usr/bin/env python3
"""Ablate deterministic and local-LLM candidate generators on held-out states."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_training import load_jsonl  # noqa: E402
from agent_world_model.phase3_candidates import (  # noqa: E402
    AXTreeCandidateGenerator,
    LLMConstrainedCandidateGenerator,
    candidate_set_entropy,
    validate_action,
)
from agent_world_model.reactive_agent import parse_elements  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dataset-dir", type=Path, default=PROJECT_ROOT / "data" / "phase2_p1")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "candidate_generator_ablation_gpu.json")
    return parser.parse_args()


def _raw_index() -> dict[tuple[str, int, str], dict[str, Any]]:
    result: dict[tuple[str, int, str], dict[str, Any]] = {}
    for directory in (
        PROJECT_ROOT / "data" / "trajectories_phase2",
        PROJECT_ROOT / "data" / "trajectories_phase2_risk",
        PROJECT_ROOT / "data" / "trajectories_phase2_counterfactual",
        PROJECT_ROOT / "data" / "trajectories_phase2_expansion",
        PROJECT_ROOT / "data" / "trajectories_phase2_expansion_b",
        PROJECT_ROOT / "data" / "trajectories_phase2_expansion_c",
    ):
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.jsonl")):
            for record in load_jsonl(path):
                result[(str(record.get("episode_id", "")), int(record.get("step_index", 0)), str(record.get("action", "")))] = record
    return result


class LocalTransformersCompletion:
    """JSON completion callable for the strict phase-three LLM adapter."""

    def __init__(self, model_id: str, device: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="auto" if device.startswith("cuda") else None,
        )
        self.model.eval()

    def __call__(self, prompt: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You select browser-agent candidates. Return one JSON object only and follow "
                    "the exact output schema in the request. Do not use markdown or add keys. "
                    "When a candidate pool is supplied, use only its integer indices."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        rendered = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(rendered, return_tensors="pt", truncation=True, max_length=6144)
        model_device = next(self.model.parameters()).device
        inputs = {key: value.to(model_device) for key, value in inputs.items()}
        with self.torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=384,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0, inputs["input_ids"].shape[1] :]
        text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        start, end = text.find("{"), text.rfind("}")
        return text[start : end + 1] if start >= 0 and end >= start else text


def _summarize(rows: list[dict[str, Any]], failures: int) -> dict[str, Any]:
    successful = [row for row in rows if row.get("generated")]
    return {
        "examples_attempted": len(rows),
        "generation_successes": len(successful),
        "generation_failures": failures,
        "strict_json_success_rate": len(successful) / max(1, len(rows)),
        "candidate_schema_valid_rate": sum(row.get("valid", 0) for row in successful) / max(1, sum(row.get("candidate_count", 0) for row in successful)),
        "recorded_action_recall_at_k": sum(bool(row.get("source_covered")) for row in successful) / max(1, len(successful)),
        "average_candidate_count": statistics.fmean([row["candidate_count"] for row in successful]) if successful else 0.0,
        "average_type_entropy": statistics.fmean([row["entropy"] for row in successful]) if successful else 0.0,
        "latency_ms_mean": statistics.fmean([row["latency_ms"] for row in successful]) if successful else 0.0,
    }


def main() -> int:
    args = parse_args()
    dataset_dir = args.dataset_dir if args.dataset_dir.is_absolute() else PROJECT_ROOT / args.dataset_dir
    test_rows = load_jsonl(dataset_dir / "test.jsonl")
    raw = _raw_index()
    matched = []
    for record in test_rows:
        source = raw.get((record["episode_id"], int(record["step_index"]), record["action"]))
        if source is not None:
            matched.append((record, source))
        if len(matched) >= args.limit:
            break
    rule_generator = AXTreeCandidateGenerator(max_candidates=args.max_candidates)
    completion = LocalTransformersCompletion(args.model, args.device)
    llm_generator = LLMConstrainedCandidateGenerator(
        completion,
        max_candidates=args.max_candidates,
        pool_size=24,
    )
    all_rows: dict[str, list[dict[str, Any]]] = {"rules": [], "local_llm": []}
    failures = {"rules": 0, "local_llm": 0}
    for canonical, source in matched:
        state = source["state"]
        visible = {element.bid for element in parse_elements(state["axtree"]["text"])}
        for name, generator in (("rules", rule_generator), ("local_llm", llm_generator)):
            started = time.perf_counter()
            try:
                candidates = generator.generate(state)
                latency_ms = (time.perf_counter() - started) * 1000.0
                actions = [item.action for item in candidates]
                all_rows[name].append(
                    {
                        "example_id": canonical["example_id"],
                        "generated": True,
                        "candidate_count": len(candidates),
                        "valid": sum(validate_action(action, visible)[0] for action in actions),
                        "source_covered": canonical["action"] in actions,
                        "entropy": candidate_set_entropy(candidates),
                        "latency_ms": latency_ms,
                        "actions": actions,
                    }
                )
            except Exception as error:
                failures[name] += 1
                all_rows[name].append({"example_id": canonical["example_id"], "generated": False, "error": repr(error)})
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": args.device,
        "model_id": args.model,
        "provider": "local_transformers",
        "credential_required": False,
        "held_out_examples_requested": args.limit,
        "held_out_examples_matched": len(matched),
        "metrics": {name: _summarize(rows, failures[name]) for name, rows in all_rows.items()},
        "interpretation_limits": [
            "This ablation evaluates candidate-set validity and recorded-action recall, not live task success.",
            "The selected local model is text-only; VLM image grounding remains untested.",
        ],
        "rows": all_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0 if len(matched) and failures["local_llm"] < len(matched) else 2


if __name__ == "__main__":
    raise SystemExit(main())
