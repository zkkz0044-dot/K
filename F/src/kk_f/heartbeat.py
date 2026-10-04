"""F05 deterministic heartbeat freshness gate."""

from __future__ import annotations

from datetime import datetime, timezone
import re

HEARTBEAT_VERSION = "0.1"
HEARTBEAT_KEYS = frozenset({"version", "sequence", "observed_at"})
RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$"
)


class HeartbeatError(ValueError):
    """Raised when heartbeat input violates the F05 contract."""


def _parse_rfc3339(value: object, where: str) -> datetime:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        raise HeartbeatError(f"{where}: strict RFC3339 timestamp required")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HeartbeatError(f"{where}: invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HeartbeatError(f"{where}: timezone required")
    return parsed.astimezone(timezone.utc)


def _strict_int(value: object, where: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise HeartbeatError(f"{where}: integer >= {minimum} required")
    return value


def validate_heartbeat(value: object) -> dict:
    if not isinstance(value, dict):
        raise HeartbeatError("heartbeat: object required")
    if frozenset(value) != HEARTBEAT_KEYS:
        raise HeartbeatError("heartbeat: exact keys required")
    if value["version"] != HEARTBEAT_VERSION:
        raise HeartbeatError("heartbeat: unsupported version")
    _strict_int(value["sequence"], "heartbeat.sequence")
    _parse_rfc3339(value["observed_at"], "heartbeat.observed_at")
    return value


def evaluate_freshness(
    heartbeat: object,
    *,
    now: object,
    healthy_within_seconds: object,
    degraded_within_seconds: object,
) -> dict:
    """Classify freshness from explicit inputs; never reads the host clock."""
    heartbeat = validate_heartbeat(heartbeat)
    now_dt = _parse_rfc3339(now, "now")
    healthy = _strict_int(healthy_within_seconds, "healthy_within_seconds", 1)
    degraded = _strict_int(degraded_within_seconds, "degraded_within_seconds", 1)
    if degraded < healthy:
        raise HeartbeatError("degraded threshold must be >= healthy threshold")

    observed = _parse_rfc3339(heartbeat["observed_at"], "heartbeat.observed_at")
    age = (now_dt - observed).total_seconds()
    if age < 0:
        raise HeartbeatError("heartbeat cannot be from the future")

    if age <= healthy:
        status = "HEALTHY"
    elif age <= degraded:
        status = "DEGRADED"
    else:
        status = "FAILED"
    return {
        "version": HEARTBEAT_VERSION,
        "sequence": heartbeat["sequence"],
        "status": status,
        "age_seconds": age,
    }
