from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    executor_id: str
    verifier_id: str
    enabled: bool = True


class ActionRegistryError(ValueError):
    pass


_REGISTRY = {
    "A01_READ_PROJECT_STATE": ActionSpec(
        "A01_READ_PROJECT_STATE", "READ_PROJECT_STATE", "VERIFY_A01"
    ),
    "A02_READ_F_STATUS": ActionSpec("A02_READ_F_STATUS", "READ_F_STATUS", "VERIFY_A02"),
    "A03_RUN_F_SMOKE_TEST": ActionSpec("A03_RUN_F_SMOKE_TEST", "RUN_F_SMOKE_TEST", "VERIFY_A03"),
    "A04_WRITE_K_DECISION_LOG": ActionSpec(
        "A04_WRITE_K_DECISION_LOG", "WRITE_K_DECISION_MARKER", "VERIFY_A04"
    ),
    "A05_NO_ACTION": ActionSpec("A05_NO_ACTION", "NO_ACTION", "VERIFY_A05"),
}

ALLOWED_ACTIONS = frozenset(_REGISTRY)


def get_action_spec(action_id: object) -> ActionSpec:
    if not isinstance(action_id, str) or action_id not in _REGISTRY:
        raise ActionRegistryError("unknown action_id")
    spec = _REGISTRY[action_id]
    if not spec.enabled:
        raise ActionRegistryError("action disabled")
    return spec
