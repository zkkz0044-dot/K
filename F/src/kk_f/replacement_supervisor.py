"""F14 bounded replacement coordination for a failed managed process."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .managed_process import ManagedProcess, ManagedProcessError, launch_managed
from .restart_ledger import RestartLedgerError, evaluate_and_record


class ReplacementSupervisorError(RuntimeError):
    """Raised when F14 cannot safely coordinate a replacement."""


@dataclass(frozen=True)
class ReplacementResult:
    observed_status: str
    decision: str
    attempts: int
    max_attempts: int
    generation: int
    replacement: Optional[ManagedProcess]


def evaluate_and_replace(
    ledger_directory: str,
    current: ManagedProcess,
    replacement_spec: object,
) -> ReplacementResult:
    """Observe current process, durably account restart policy, and replace only on approval.

    The durable restart attempt is committed before replacement launch. Therefore a launch
    failure still consumes the approved attempt, which is intentionally fail-closed and
    prevents an unbounded retry loop around a bad candidate.
    """
    if not isinstance(current, ManagedProcess):
        raise ReplacementSupervisorError("current must be a ManagedProcess")

    observed = current.observe()
    status = observed["status"]
    try:
        ledger = evaluate_and_record(ledger_directory, status)
    except RestartLedgerError as exc:
        raise ReplacementSupervisorError("restart ledger evaluation failed") from exc

    decision = ledger["last_decision"]
    if decision != "REPLACE_INSTANCE":
        return ReplacementResult(
            observed_status=status,
            decision=decision,
            attempts=ledger["attempts"],
            max_attempts=ledger["max_attempts"],
            generation=ledger["generation"],
            replacement=None,
        )

    try:
        replacement = launch_managed(replacement_spec)
    except ManagedProcessError as exc:
        raise ReplacementSupervisorError(
            "replacement launch failed after durable attempt was consumed"
        ) from exc

    return ReplacementResult(
        observed_status=status,
        decision=decision,
        attempts=ledger["attempts"],
        max_attempts=ledger["max_attempts"],
        generation=ledger["generation"],
        replacement=replacement,
    )
