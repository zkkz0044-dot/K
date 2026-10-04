"""FP03 deterministic restart backoff computed from durable ledger state."""

from __future__ import annotations

from .heartbeat import HeartbeatError, _parse_rfc3339


class RestartBackoffError(ValueError):
    """Raised when backoff inputs are invalid or time moves backwards."""


def _positive_number(value: object, where: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or value <= 0:
        raise RestartBackoffError(f"{where}: positive number required")
    result = float(value)
    if result == float("inf") or result != result:
        raise RestartBackoffError(f"{where}: finite number required")
    return result


def evaluate_restart_backoff(
    ledger: object,
    *,
    now: object,
    base_delay_seconds: object,
    max_delay_seconds: object,
) -> dict:
    if not isinstance(ledger, dict):
        raise RestartBackoffError("ledger: object required")
    attempts = ledger.get("attempts")
    if type(attempts) is not int or attempts < 0:
        raise RestartBackoffError("ledger.attempts: non-negative integer required")
    last_attempt_at = ledger.get("last_attempt_at")
    try:
        now_dt = _parse_rfc3339(now, "now")
    except HeartbeatError as exc:
        raise RestartBackoffError("now: strict RFC3339 required") from exc
    base = _positive_number(base_delay_seconds, "base_delay_seconds")
    cap = _positive_number(max_delay_seconds, "max_delay_seconds")
    if cap < base:
        raise RestartBackoffError("max_delay_seconds must be >= base_delay_seconds")

    if attempts == 0 or last_attempt_at is None:
        return {
            "allowed": True,
            "attempts": attempts,
            "delay_seconds": 0.0,
            "remaining_seconds": 0.0,
        }
    try:
        last_dt = _parse_rfc3339(last_attempt_at, "last_attempt_at")
    except HeartbeatError as exc:
        raise RestartBackoffError("last_attempt_at invalid") from exc
    elapsed = (now_dt - last_dt).total_seconds()
    if elapsed < 0:
        raise RestartBackoffError("now cannot precede last_attempt_at")
    delay = min(base * (2 ** (attempts - 1)), cap)
    remaining = max(0.0, delay - elapsed)
    return {
        "allowed": remaining == 0.0,
        "attempts": attempts,
        "delay_seconds": delay,
        "remaining_seconds": remaining,
    }
