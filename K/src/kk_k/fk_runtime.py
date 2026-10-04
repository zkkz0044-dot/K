"""Canonical governed K→FK runtime path for the merged system."""

from __future__ import annotations

import json
import secrets

from .audit_witness import AuditWitnessError, append_remote_event
from .fk_client import DEFAULT_ADDRESS, FKClientError, submit
from .governance import GovernanceError, govern, load_policy
from .verifier import VerificationError, verify_receipt

DEFAULT_POLICY_PATH = "/root/K/K/K06_POLICY.json"
F_HUMAN_GATED_ACTIONS = frozenset({"A03_RUN_F_SMOKE_TEST"})
PRIVILEGED_AUDIT_SUBJECT = "privileged_attempt"


class FKRuntimeError(RuntimeError):
    pass


def _audit_privileged_attempt(action_id: str, governance_outcome: str) -> None:
    summary = json.dumps(
        {"action_id": action_id, "governance": governance_outcome},
        sort_keys=True,
        separators=(",", ":"),
    )
    append_remote_event(
        event_id="privileged-" + secrets.token_hex(8),
        kind="EXECUTION",
        subject=PRIVILEGED_AUDIT_SUBJECT,
        summary=summary,
    )


def execute_governed(
    action_id: str,
    history: list[str],
    *,
    policy_path: str = DEFAULT_POLICY_PATH,
    address: str = DEFAULT_ADDRESS,
) -> dict:
    try:
        policy = load_policy(policy_path)
        decision = govern(action_id, policy, history)
    except GovernanceError as exc:
        raise FKRuntimeError("K governance rejected request") from exc

    if decision.action_id in F_HUMAN_GATED_ACTIONS:
        if decision.outcome != "REQUIRE_HUMAN":
            raise FKRuntimeError("human-gated action lost REQUIRE_HUMAN policy")
        try:
            _audit_privileged_attempt(decision.action_id, decision.outcome)
        except AuditWitnessError as exc:
            raise FKRuntimeError("privileged audit witness rejected request") from exc
        # Audit success only allows asking F to evaluate F's own approval state.
        # It is not approval and carries no token/boolean/path from K.
    elif decision.outcome == "REQUIRE_HUMAN":
        return {
            "status": "REQUIRE_HUMAN",
            "action_id": decision.action_id,
            "reason": decision.reason,
            "f_called": False,
        }
    elif decision.outcome != "ALLOW":
        return {
            "status": decision.outcome,
            "action_id": decision.action_id,
            "reason": decision.reason,
            "f_called": False,
        }

    try:
        receipt = submit(decision.action_id, address=address)
        verified = verify_receipt(decision.action_id, receipt)
    except (FKClientError, VerificationError) as exc:
        raise FKRuntimeError("FK transport/receipt rejected") from exc
    return {
        "status": verified.result,
        "action_id": decision.action_id,
        "f_called": True,
        "receipt": receipt,
    }
