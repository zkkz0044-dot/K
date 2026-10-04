"""F17 durable F02 audit records for F16 supervision outcomes."""

from __future__ import annotations

from .evidence import EvidenceError, append
from .health_supervisor import HealthSupervisionResult


class SupervisionEvidenceError(RuntimeError):
    """Raised when a supervision outcome cannot be durably audited."""


def record_supervision(
    evidence_directory: str,
    result: HealthSupervisionResult,
    *,
    message_id: object,
    timestamp: object,
) -> str:
    if not isinstance(result, HealthSupervisionResult):
        raise SupervisionEvidenceError("result must be a HealthSupervisionResult")

    replacement_pid = None
    if result.replacement is not None:
        replacement_pid = result.replacement.pid

    record = {
        "protocol_version": "0.1",
        "message_id": message_id,
        "kind": "result",
        "source_role": "supervisor",
        "target_role": "operator",
        "timestamp": timestamp,
        "status": result.health_status,
        "payload": {
            "process_status": result.process_status,
            "decision": result.decision,
            "attempts": result.attempts,
            "contained": result.contained,
            "replacement_pid": replacement_pid,
        },
        "error": None,
    }
    try:
        return append(evidence_directory, record)
    except EvidenceError as exc:
        raise SupervisionEvidenceError("supervision evidence append failed") from exc
