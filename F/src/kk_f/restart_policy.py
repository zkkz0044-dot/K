"""F07 deterministic bounded restart decision gate."""

from __future__ import annotations

from .contracts import RUNTIME_STATUSES

DECISIONS = frozenset({"NO_ACTION", "REPLACE_INSTANCE", "HOLD_FAILED"})


class RestartPolicyError(ValueError):
    """Raised when restart policy input is invalid."""


def _strict_int(value: object, where: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise RestartPolicyError(f"{where}: integer >= {minimum} required")
    return value


def decide(status: object, attempts: object, max_attempts: object) -> dict:
    if not isinstance(status, str) or status not in RUNTIME_STATUSES:
        raise RestartPolicyError("status: known runtime status required")
    attempts = _strict_int(attempts, "attempts")
    max_attempts = _strict_int(max_attempts, "max_attempts", 1)

    if attempts > max_attempts:
        raise RestartPolicyError("attempts cannot exceed max_attempts")
    if status != "FAILED":
        decision = "NO_ACTION"
    elif attempts < max_attempts:
        decision = "REPLACE_INSTANCE"
    else:
        decision = "HOLD_FAILED"

    return {
        "status": status,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "decision": decision,
    }
