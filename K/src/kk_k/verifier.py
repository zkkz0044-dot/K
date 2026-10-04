from __future__ import annotations

from dataclasses import dataclass

from .action_registry import ActionRegistryError, get_action_spec

RECEIPT_SCHEMA = "K01.F_RECEIPT.1"
FK_RECEIPT_SCHEMA = "FK01.F_RECEIPT.1"
RECEIPT_KEYS = frozenset({"schema", "action_id", "outcome", "evidence"})
VETO_REASON_CODES = frozenset(
    {
        "ACTION_DISABLED",
        "POLICY_DENY",
        "AUTHORITY_MISMATCH",
        "INVALID_REQUEST",
        "PEER_AUTH_DENY",
        "EXECUTABLE_SHA256_MISMATCH",
        "PRECHECK_FAILED",
        "RESTART_BUDGET_EXHAUSTED",
        "INTERNAL_ERROR",
        "F_STATE_INVALID",
        "AUDIT_LOG_INVALID",
        "PROCESS_EXECUTION_FAILED",
        "HUMAN_APPROVAL_REQUIRED",
        "HUMAN_APPROVAL_EXPIRED",
        "HUMAN_APPROVAL_INVALID",
    }
)
VETO_STAGES = frozenset(
    {
        "PEER_AUTH",
        "REQUEST_PARSE",
        "FK_POLICY",
        "FROZEN_AUTHORITY",
        "PROCESS_PREFLIGHT",
        "PROCESS_EXECUTOR",
        "RUNTIME_SUPERVISOR",
        "INTERNAL",
        "F_STATE",
        "F_AUDIT",
        "HUMAN_APPROVAL",
    }
)


class VerificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerificationResult:
    result: str
    action_id: str


def _exact_dict(value: object, keys: frozenset[str], label: str) -> dict:
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise VerificationError(f"{label} exact fields required")
    return value


def _verify_veto(schema: str, evidence: object) -> None:
    if schema == FK_RECEIPT_SCHEMA:
        ev = _exact_dict(
            evidence, frozenset({"kind", "reason_code", "validation_stage"}), "FK veto evidence"
        )
        if ev["validation_stage"] not in VETO_STAGES:
            raise VerificationError("invalid veto validation stage")
    else:
        ev = _exact_dict(evidence, frozenset({"kind", "reason_code"}), "veto evidence")
    if ev["kind"] != "VETO" or ev["reason_code"] not in VETO_REASON_CODES:
        raise VerificationError("invalid veto evidence")


def verify_receipt(action_id: str, receipt: object) -> VerificationResult:
    try:
        spec = get_action_spec(action_id)
    except ActionRegistryError as exc:
        raise VerificationError("unregistered action") from exc
    value = _exact_dict(receipt, RECEIPT_KEYS, "receipt")
    schema = value["schema"]
    if schema not in {RECEIPT_SCHEMA, FK_RECEIPT_SCHEMA}:
        raise VerificationError("unsupported receipt schema")
    if value["action_id"] != action_id:
        raise VerificationError("receipt action mismatch")
    outcome = value["outcome"]
    evidence = value["evidence"]

    if outcome == "VETO":
        _verify_veto(schema, evidence)
        return VerificationResult("VETO", action_id)
    if outcome != "EXECUTED":
        raise VerificationError("invalid receipt outcome")

    if spec.verifier_id == "VERIFY_A01":
        ev = _exact_dict(evidence, frozenset({"kind", "status"}), "A01 evidence")
        ok = (
            ev["kind"] == "PROJECT_STATE"
            and isinstance(ev["status"], str)
            and 0 < len(ev["status"]) <= 64
        )
    elif spec.verifier_id == "VERIFY_A02":
        ev = _exact_dict(evidence, frozenset({"kind", "status"}), "A02 evidence")
        ok = ev["kind"] == "F_STATUS" and ev["status"] in {"ACCEPTED", "DEGRADED", "FAILED"}
    elif spec.verifier_id == "VERIFY_A03":
        ev = _exact_dict(evidence, frozenset({"kind", "exit_code", "tests_failed"}), "A03 evidence")
        ok = ev["kind"] == "F_SMOKE" and ev["exit_code"] == 0 and ev["tests_failed"] == 0
    elif spec.verifier_id == "VERIFY_A04":
        ev = _exact_dict(evidence, frozenset({"kind", "appended", "durable"}), "A04 evidence")
        ok = ev["kind"] == "K_DECISION_LOG" and ev["appended"] is True and ev["durable"] is True
    elif spec.verifier_id == "VERIFY_A05":
        ev = _exact_dict(evidence, frozenset({"kind", "process_started"}), "A05 evidence")
        ok = ev["kind"] == "NO_ACTION" and ev["process_started"] is False
    else:
        raise VerificationError("unregistered action")

    return VerificationResult("PASS" if ok else "FAIL", action_id)
