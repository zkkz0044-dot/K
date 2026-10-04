"""FP04 side-effect-free production dry-run planning."""

from __future__ import annotations

from dataclasses import dataclass

from .frozen_authority import FrozenAuthorityError, authorize_process
from .process_preflight import ProcessPreflightError, verify_process_candidate
from .restart_backoff import RestartBackoffError, evaluate_restart_backoff
from .restart_ledger import RestartLedgerError, read_ledger
from .restart_policy import RestartPolicyError, decide


class DryRunError(RuntimeError):
    """Raised when a production dry-run cannot be evaluated safely."""


@dataclass(frozen=True)
class DryRunPlan:
    authority_id: str
    verified_sha256: str
    runtime_status: str
    attempts: int
    max_attempts: int
    decision: str
    backoff_delay_seconds: float
    backoff_remaining_seconds: float


def plan_runtime_action(
    authority_path: str,
    ledger_directory: str,
    process_spec: object,
    runtime_status: object,
    *,
    now: object,
    base_delay_seconds: object = 1,
    max_delay_seconds: object = 60,
) -> DryRunPlan:
    """Read and validate real production state without mutating or launching anything."""
    try:
        authorization = authorize_process(authority_path, process_spec)
    except FrozenAuthorityError as exc:
        raise DryRunError("Frozen Authority denied dry-run candidate") from exc

    try:
        verified = verify_process_candidate(process_spec)
    except ProcessPreflightError as exc:
        raise DryRunError("dry-run candidate integrity preflight failed") from exc

    try:
        ledger = read_ledger(ledger_directory)
    except RestartLedgerError as exc:
        raise DryRunError("restart ledger invalid") from exc

    if ledger["max_attempts"] != authorization["max_restart_attempts"]:
        raise DryRunError("restart ledger budget does not match Frozen Authority")

    try:
        policy = decide(runtime_status, ledger["attempts"], ledger["max_attempts"])
    except RestartPolicyError as exc:
        raise DryRunError("restart policy input invalid") from exc

    decision = policy["decision"]
    delay = 0.0
    remaining = 0.0
    if decision == "REPLACE_INSTANCE":
        try:
            backoff = evaluate_restart_backoff(
                ledger,
                now=now,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
            )
        except RestartBackoffError as exc:
            raise DryRunError("restart backoff input invalid") from exc
        delay = backoff["delay_seconds"]
        remaining = backoff["remaining_seconds"]
        if not backoff["allowed"]:
            decision = "WAIT_BACKOFF"

    return DryRunPlan(
        authority_id=authorization["authority_id"],
        verified_sha256=verified["sha256"],
        runtime_status=runtime_status,
        attempts=ledger["attempts"],
        max_attempts=ledger["max_attempts"],
        decision=decision,
        backoff_delay_seconds=delay,
        backoff_remaining_seconds=remaining,
    )
