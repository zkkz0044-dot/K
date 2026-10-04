"""F06 deterministic monotonic heartbeat stream gate."""

from __future__ import annotations

from .heartbeat import HeartbeatError, _parse_rfc3339, validate_heartbeat


class HeartbeatStreamError(ValueError):
    """Raised when a heartbeat stream violates monotonicity."""


def _validated(value: object, where: str) -> dict:
    try:
        return validate_heartbeat(value)
    except HeartbeatError as exc:
        raise HeartbeatStreamError(f"{where}: invalid heartbeat") from exc


def advance(previous: object | None, current: object) -> dict:
    """Accept only a strictly advancing heartbeat stream."""
    current = _validated(current, "current")
    if previous is None:
        return {
            "accepted": True,
            "sequence": current["sequence"],
            "observed_at": current["observed_at"],
        }

    previous = _validated(previous, "previous")
    if current["sequence"] <= previous["sequence"]:
        raise HeartbeatStreamError("sequence must strictly increase")
    previous_time = _parse_rfc3339(previous["observed_at"], "previous.observed_at")
    current_time = _parse_rfc3339(current["observed_at"], "current.observed_at")
    if current_time <= previous_time:
        raise HeartbeatStreamError("observed_at must strictly increase")

    return {
        "accepted": True,
        "sequence": current["sequence"],
        "observed_at": current["observed_at"],
    }
