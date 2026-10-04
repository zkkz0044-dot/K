"""F15 health gate combining real managed-process state with explicit heartbeat evidence."""

from __future__ import annotations

from .heartbeat import HeartbeatError, evaluate_freshness
from .managed_process import ManagedProcess


class ManagedHealthError(ValueError):
    """Raised when F15 cannot safely establish managed-process health."""


def evaluate_managed_health(
    current: ManagedProcess,
    heartbeat: object,
    *,
    now: object,
    healthy_within_seconds: object,
    degraded_within_seconds: object,
) -> dict:
    if not isinstance(current, ManagedProcess):
        raise ManagedHealthError("current must be a ManagedProcess")

    observed = current.observe()
    process_status = observed["status"]
    if process_status != "RUNNING":
        return {
            "pid": observed["pid"],
            "process_status": process_status,
            "status": process_status,
            "heartbeat_sequence": None,
            "heartbeat_age_seconds": None,
        }

    try:
        freshness = evaluate_freshness(
            heartbeat,
            now=now,
            healthy_within_seconds=healthy_within_seconds,
            degraded_within_seconds=degraded_within_seconds,
        )
    except HeartbeatError as exc:
        raise ManagedHealthError("heartbeat evidence invalid") from exc

    return {
        "pid": observed["pid"],
        "process_status": process_status,
        "status": freshness["status"],
        "heartbeat_sequence": freshness["sequence"],
        "heartbeat_age_seconds": freshness["age_seconds"],
    }
