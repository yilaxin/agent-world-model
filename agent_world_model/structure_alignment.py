"""Trainable task-to-GUI element alignment used by the W1 planner."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn

from .phase2_schema import encode_action
from .reactive_agent import ElementRef, parse_elements


FEATURE_NAMES = (
    "semantic_overlap",
    "exact_name",
    "role_compatible",
    "intent_compatible",
    "depth_normalized",
    "task_phase",
    "history_repeat",
    "name_length",
)
_WORD_RE = re.compile(r"[\w.-]+", re.UNICODE)
_INPUT_ROLES = {"textbox", "searchbox", "combobox"}
_CLICK_ROLES = {"button", "link", "checkbox", "radio", "option", "menuitem", "tab"}
_STOPWORDS = {
    "a", "an", "and", "button", "click", "field", "fill", "in", "into",
    "link", "on", "open", "please", "select", "text", "the", "to", "type",
}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(text)
        if len(token) > 1 and token.lower() not in _STOPWORDS
    }


def _state_value(state: Mapping[str, Any] | Any, key: str, default: Any = None) -> Any:
    if isinstance(state, Mapping):
        return state.get(key, default)
    return getattr(state, key, default)


def _axtree_text(state: Mapping[str, Any] | Any) -> str:
    value = _state_value(state, "axtree", "")
    if isinstance(value, Mapping):
        return str(value.get("text", ""))
    return str(getattr(value, "text", "") or value or "")


def alignment_features(
    goal: str,
    element: ElementRef,
    action_type: str,
    *,
    step_index: int = 0,
    recent_actions: Sequence[str] = (),
) -> tuple[list[float], dict[str, float]]:
    goal_terms = _tokens(goal)
    name_terms = _tokens(element.name)
    overlap = len(goal_terms & name_terms) / max(1, len(name_terms))
    exact = float(bool(element.name and element.name.lower() in goal.lower()))
    role_compatible = float(
        (action_type in {"fill", "type"} and element.role in _INPUT_ROLES)
        or (action_type == "click" and element.role in _CLICK_ROLES)
        or (action_type == "select_option" and element.role in {"combobox", "option"})
    )
    input_intent = bool(re.search(r"\b(?:enter|type|input|fill|write|search)\b|输入|填写|键入|搜索", goal, re.I))
    click_intent = bool(re.search(r"\b(?:click|open|choose|select|press)\b|点击|打开|选择", goal, re.I))
    intent_compatible = float(
        (input_intent and action_type in {"fill", "type", "select_option"})
        or (click_intent and action_type == "click")
        or (not input_intent and not click_intent)
    )
    repeated = float(
        any(element.bid in action or action.strip() == element.raw_line for action in recent_actions[-5:])
    )
    values = [
        max(overlap, exact),
        exact,
        role_compatible,
        intent_compatible,
        min(1.0, element.depth / 10.0),
        min(1.0, max(0, step_index) / 5.0),
        repeated,
        min(1.0, len(element.name) / 40.0),
    ]
    return values, dict(zip(FEATURE_NAMES, values))


@dataclass(frozen=True)
class StructureAlignmentConfig:
    input_dim: int = len(FEATURE_NAMES)
    hidden_dim: int = 24
    dropout: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StructureAlignmentModel(nn.Module):
    def __init__(self, config: StructureAlignmentConfig | None = None) -> None:
        super().__init__()
        self.config = config or StructureAlignmentConfig()
        self.network = nn.Sequential(
            nn.Linear(self.config.input_dim, self.config.hidden_dim),
            nn.GELU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.hidden_dim, 1),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.network(features).squeeze(-1)


class StructureAlignmentPredictor:
    """Score a candidate target with a learned dynamic alignment model."""

    def __init__(self, checkpoint_path: str | Path, device: str = "cpu") -> None:
        self.device = torch.device(device)
        saved = torch.load(Path(checkpoint_path), map_location=self.device, weights_only=True)
        self.model = StructureAlignmentModel(
            StructureAlignmentConfig(**saved["model_config"])
        ).to(self.device)
        self.model.load_state_dict(saved["model_state_dict"])
        self.model.eval()

    @torch.no_grad()
    def score(
        self,
        state: Mapping[str, Any] | Any,
        action: str,
        recent_actions: Sequence[str] = (),
    ) -> tuple[float, dict[str, Any]]:
        goal = str(_state_value(state, "goal", "") or "")
        _, parsed = encode_action(action)
        targets = parsed["target_element_ids"]
        if not targets:
            return 0.15, {"learned": True, "target_visible": None}
        element = next(
            (item for item in parse_elements(_axtree_text(state)) if item.bid == targets[0]),
            None,
        )
        if element is None:
            return 0.0, {"learned": True, "target_visible": False}
        features, components = alignment_features(
            goal,
            element,
            parsed["action_type"],
            step_index=int(_state_value(state, "step_index", 0) or 0),
            recent_actions=recent_actions,
        )
        tensor = torch.tensor(features, dtype=torch.float32, device=self.device).unsqueeze(0)
        probability = float(torch.sigmoid(self.model(tensor))[0])
        return probability, {
            "learned": True,
            "target_visible": True,
            "feature_values": components,
        }


def load_alignment_checkpoint(path: str | Path, device: str = "cpu") -> StructureAlignmentPredictor:
    return StructureAlignmentPredictor(path, device=device)


def checkpoint_metadata(path: str | Path) -> dict[str, Any]:
    saved = torch.load(Path(path), map_location="cpu", weights_only=True)
    return {
        "model_config": saved["model_config"],
        "seed": saved.get("seed"),
        "validation_mrr": saved.get("validation_mrr"),
    }
