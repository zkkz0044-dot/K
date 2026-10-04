"""F01 strict protocol contract validation.

No network, filesystem, subprocess, time generation, or dynamic code execution occurs here.
"""

from __future__ import annotations

from datetime import datetime
import re
import uuid

PROTOCOL_VERSION = "0.1"

ROLES = frozenset({"frozen_authority", "worker", "supervisor", "operator", "external_controller"})
KINDS = frozenset({"heartbeat", "progress", "result", "fault", "control_request", "control_result"})
RUNTIME_STATUSES = frozenset(
    {"READY", "RUNNING", "HEALTHY", "DEGRADED", "BLOCKED", "FAILED", "STOPPED"}
)
ERROR_CODES = frozenset(
    {
        "INVALID_SCHEMA",
        "UNSUPPORTED_PROTOCOL",
        "UNKNOWN_ROLE",
        "UNKNOWN_STATUS",
        "UNKNOWN_KIND",
        "ILLEGAL_TRANSITION",
        "INTEGRITY_FAILURE",
        "TIMEOUT",
        "RESOURCE_LIMIT",
        "AUTHORITY_DENIED",
        "INTERNAL_ERROR",
    }
)
MESSAGE_KEYS = frozenset(
    {
        "protocol_version",
        "message_id",
        "kind",
        "source_role",
        "target_role",
        "timestamp",
        "status",
        "payload",
        "error",
    }
)
ERROR_KEYS = frozenset({"code", "message", "retryable", "detail"})
LOWER_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


class ContractError(ValueError):
    """Raised when a cross-component message violates the frozen F01 contract."""


def _repr_sorted(values) -> list[str]:
    return sorted(repr(value) for value in values)


def _require_exact_keys(value: dict, expected: frozenset[str], where: str) -> None:
    actual = frozenset(value.keys())
    if actual != expected:
        missing = _repr_sorted(expected - actual)
        unknown = _repr_sorted(actual - expected)
        raise ContractError(f"{where}: exact keys required; missing={missing}; unknown={unknown}")


def _require_enum(value: object, allowed: frozenset[str], where: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ContractError(f"{where}: unknown or invalid value")
    return value


def _validate_uuid(value: object) -> None:
    if not isinstance(value, str) or not LOWER_UUID_RE.fullmatch(value):
        raise ContractError("message_id: canonical lowercase UUID required")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ContractError("message_id: invalid UUID") from exc
    if str(parsed) != value:
        raise ContractError("message_id: non-canonical UUID")


def _validate_timestamp(value: object) -> None:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        raise ContractError("timestamp: strict RFC3339 string with timezone required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError("timestamp: invalid calendar/time value") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("timestamp: explicit timezone required")


def _validate_error(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ContractError("error: null or object required")
    _require_exact_keys(value, ERROR_KEYS, "error")
    _require_enum(value["code"], ERROR_CODES, "error.code")
    if not isinstance(value["message"], str):
        raise ContractError("error.message: string required")
    if type(value["retryable"]) is not bool:
        raise ContractError("error.retryable: boolean required")
    if not isinstance(value["detail"], dict):
        raise ContractError("error.detail: object required")


def validate_message(message: object) -> dict:
    """Validate and return the original message; reject ambiguity fail-closed."""
    if not isinstance(message, dict):
        raise ContractError("message: object required")
    _require_exact_keys(message, MESSAGE_KEYS, "message")
    if (
        not isinstance(message["protocol_version"], str)
        or message["protocol_version"] != PROTOCOL_VERSION
    ):
        raise ContractError("protocol_version: unsupported")
    _validate_uuid(message["message_id"])
    _require_enum(message["kind"], KINDS, "kind")
    _require_enum(message["source_role"], ROLES, "source_role")
    _require_enum(message["target_role"], ROLES, "target_role")
    _validate_timestamp(message["timestamp"])
    _require_enum(message["status"], RUNTIME_STATUSES, "status")
    if not isinstance(message["payload"], dict):
        raise ContractError("payload: object required")
    _validate_error(message["error"])
    return message
