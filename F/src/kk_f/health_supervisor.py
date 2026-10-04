"""F16 health-evidence containment and bounded replacement coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .managed_health import ManagedHealthError, evaluate_managed_health
from .managed_process import ManagedProcess, ManagedProcessError, launch_managed
from .restart_backoff import RestartBackoffError, evaluate_restart_backoff
from .restart_ledger import RestartLedgerError, evaluate_and_record, read_ledger


class HealthSupervisorError(RuntimeError):
    """Raised when F16 cannot safely contain or replace an unhealthy process."""


@dataclass(frozen=True)
class HealthSupervisionResult:
    health_status: str
    process_status: str
    decision: str
    attempts: int
    contained: bool
    replacement: Optional[ManagedProcess]


def supervise_once(
    ledger_directory: str,
    current: ManagedProcess,
    heartbeat: object,
    replacement_spec: object,
    *,
    now: object,
    healthy_within_seconds: object,
    degraded_within_seconds: object,
    grace_seconds: object,
    base_delay_seconds: object = 1,
    max_delay_seconds: object = 60,
) -> HealthSupervisionResult:
    try:
        health = evaluate_managed_health(
            current,
            heartbeat,
            now=now,
            healthy_within_seconds=healthy_within_seconds,
            degraded_within_seconds=degraded_within_seconds,
        )
    except ManagedHealthError as exc:
        raise HealthSupervisorError("managed health evaluation failed") from exc

    health_status = health["status"]
    process_status = health["process_status"]
    if health_status != "FAILED":
        return HealthSupervisionResult(
            health_status=health_status,
            process_status=process_status,
            decision="NO_ACTION",
            attempts=-1,
            contained=False,
            replacement=None,
        )

    contained = False
    if process_status == "RUNNING":
        try:
            current.stop(grace_seconds=grace_seconds)
        except ManagedProcessError as exc:
            raise HealthSupervisorError("failed to contain unhealthy running process") from exc
        contained = True

    try:
        before = read_ledger(ledger_directory)
    except RestartLedgerError as exc:
        raise HealthSupervisorError("restart ledger read failed") from exc

    if before["attempts"] < before["max_attempts"]:
        try:
            backoff = evaluate_restart_backoff(
                before,
                now=now,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
            )
        except RestartBackoffError as exc:
            raise HealthSupervisorError("restart backoff evaluation failed") from exc
        if not backoff["allowed"]:
            return HealthSupervisionResult(
                health_status=health_status,
                process_status=process_status,
                decision="WAIT_BACKOFF",
                attempts=before["attempts"],
                contained=contained,
                replacement=None,
            )

    try:
        attempted_at = now if before["attempts"] < before["max_attempts"] else None
        ledger = evaluate_and_record(ledger_directory, "FAILED", attempted_at=attempted_at)
    except RestartLedgerError as exc:
        raise HealthSupervisorError("restart ledger evaluation failed") from exc

    decision = ledger["last_decision"]
    if decision != "REPLACE_INSTANCE":
        return HealthSupervisionResult(
            health_status=health_status,
            process_status=process_status,
            decision=decision,
            attempts=ledger["attempts"],
            contained=contained,
            replacement=None,
        )

    try:
        replacement = launch_managed(replacement_spec)
    except ManagedProcessError as exc:
        raise HealthSupervisorError(
            "replacement launch failed after durable attempt was consumed"
        ) from exc

    return HealthSupervisionResult(
        health_status=health_status,
        process_status=process_status,
        decision=decision,
        attempts=ledger["attempts"],
        contained=contained,
        replacement=replacement,
    )
