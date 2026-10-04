"""F03 deterministic runtime lifecycle transition gate."""

from __future__ import annotations

from typing import Final

from .contracts import RUNTIME_STATUSES


class LifecycleError(ValueError):
    """Raised when a lifecycle state or transition is invalid."""


LEGAL_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "READY": frozenset({"RUNNING", "STOPPED"}),
    "RUNNING": frozenset({"HEALTHY", "DEGRADED", "BLOCKED", "FAILED", "STOPPED"}),
    "HEALTHY": frozenset({"DEGRADED", "BLOCKED", "FAILED", "STOPPED"}),
    "DEGRADED": frozenset({"HEALTHY", "BLOCKED", "FAILED", "STOPPED"}),
    "BLOCKED": frozenset({"RUNNING", "DEGRADED", "FAILED", "STOPPED"}),
    "FAILED": frozenset({"STOPPED"}),
    "STOPPED": frozenset(),
}

if frozenset(LEGAL_TRANSITIONS) != RUNTIME_STATUSES:
    raise RuntimeError("F03 transition table does not cover frozen F01 statuses")


def _require_state(value: object, where: str) -> str:
    if not isinstance(value, str) or value not in RUNTIME_STATUSES:
        raise LifecycleError(f"{where}: unknown or invalid runtime state")
    return value


def allowed_targets(current: object) -> tuple[str, ...]:
    state = _require_state(current, "current")
    return tuple(sorted(LEGAL_TRANSITIONS[state]))


def evaluate_transition(current: object, target: object) -> dict:
    source = _require_state(current, "current")
    destination = _require_state(target, "target")
    if source == destination:
        return {"from": source, "to": destination, "changed": False}
    if destination not in LEGAL_TRANSITIONS[source]:
        raise LifecycleError("requested runtime transition is not permitted")
    return {"from": source, "to": destination, "changed": True}
