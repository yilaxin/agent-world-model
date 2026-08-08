"""Browser-agent world-model package.

Imports are lazy so phase-two dataset tooling can run on a data-only machine
without first installing BrowserGym or PyTorch.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ActionDecision",
    "BaselineConfig",
    "EncodedState",
    "EncoderConfig",
    "EpisodeResult",
    "ExtractionLimits",
    "PrunedText",
    "ReactiveAgent",
    "StateEncoderV1",
    "StateExtractor",
    "StateSnapshot",
    "TrajectoryLogger",
    "Phase3WorldModelAgent",
    "load_trajectory",
    "run_baseline_episode",
]

_EXPORTS = {
    "ActionDecision": (".reactive_agent", "ActionDecision"),
    "BaselineConfig": (".baseline", "BaselineConfig"),
    "EncodedState": (".encoder", "EncodedState"),
    "EncoderConfig": (".encoder", "EncoderConfig"),
    "EpisodeResult": (".baseline", "EpisodeResult"),
    "ExtractionLimits": (".state", "ExtractionLimits"),
    "PrunedText": (".state", "PrunedText"),
    "ReactiveAgent": (".reactive_agent", "ReactiveAgent"),
    "StateEncoderV1": (".encoder", "StateEncoderV1"),
    "StateExtractor": (".state", "StateExtractor"),
    "StateSnapshot": (".state", "StateSnapshot"),
    "TrajectoryLogger": (".trajectory", "TrajectoryLogger"),
    "Phase3WorldModelAgent": (".phase3_agent", "Phase3WorldModelAgent"),
    "load_trajectory": (".trajectory", "load_trajectory"),
    "run_baseline_episode": (".baseline", "run_baseline_episode"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
