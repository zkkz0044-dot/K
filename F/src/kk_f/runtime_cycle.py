"""F20 authority-gated, monotonic-heartbeat, audited supervision cycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .frozen_authority import FrozenAuthorityError, authorize_process
from .heartbeat_stream import HeartbeatStreamError, advance
from .health_supervisor import HealthSupervisorError, HealthSupervisionResult, supervise_once
from .managed_process import ManagedProcess
from .restart_ledger import RestartLedgerError, read_ledger
from .supervision_evidence import SupervisionEvidenceError, record_supervision


class RuntimeCycleError(RuntimeError):
    """Raised when an integrated F20 runtime cycle fails closed."""


@dataclass(frozen=True)
class RuntimeCycleResult:
    supervision: HealthSupervisionResult
    current: Optional[ManagedProcess]
    accepted_heartbeat: dict
    evidence_hash: str


def run_cycle(
    authority_path: str,
    ledger_directory: str,
    evidence_directory: str,
    current: ManagedProcess,
    heartbeat: object,
    replacement_spec: object,
    *,
    previous_heartbeat: object | None,
    now: object,
    healthy_within_seconds: object,
    degraded_within_seconds: object,
    grace_seconds: object,
    message_id: object,
    timestamp: object,
    base_delay_seconds: object = 1,
    max_delay_seconds: object = 60,
    _allow_identical_poll_snapshot: bool = False,
) -> RuntimeCycleResult:
    try:
        authorization = authorize_process(authority_path, replacement_spec)
    except FrozenAuthorityError as exc:
        raise RuntimeCycleError("Frozen Authority denied cycle candidate") from exc

    try:
        ledger = read_ledger(ledger_directory)
    except RestartLedgerError as exc:
        raise RuntimeCycleError("restart ledger invalid") from exc
    if ledger["max_attempts"] != authorization["max_restart_attempts"]:
        raise RuntimeCycleError("restart ledger budget does not match Frozen Authority")

    try:
        # A file-backed heartbeat is sampled by the production daemon. Two polls may
        # observe the exact same immutable snapshot before the writer publishes a new
        # record. That is not a second heartbeat event. Strict monotonic validation
        # remains the default; only the daemon's explicit sampling mode may re-use an
        # identical snapshot for freshness supervision. Any changed/replayed/regressed
        # record still goes through the strict stream gate and fails closed.
        if (
            _allow_identical_poll_snapshot
            and previous_heartbeat is not None
            and heartbeat == previous_heartbeat
        ):
            stream = advance(None, heartbeat)
        else:
            stream = advance(previous_heartbeat, heartbeat)
    except HeartbeatStreamError as exc:
        raise RuntimeCycleError("heartbeat stream rejected") from exc

    try:
        supervision = supervise_once(
            ledger_directory,
            current,
            heartbeat,
            replacement_spec,
            now=now,
            healthy_within_seconds=healthy_within_seconds,
            degraded_within_seconds=degraded_within_seconds,
            grace_seconds=grace_seconds,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
        )
    except HealthSupervisorError as exc:
        raise RuntimeCycleError("health supervision failed") from exc

    try:
        evidence_hash = record_supervision(
            evidence_directory,
            supervision,
            message_id=message_id,
            timestamp=timestamp,
        )
    except SupervisionEvidenceError as exc:
        if supervision.replacement is not None:
            try:
                supervision.replacement.stop(grace_seconds=grace_seconds)
            except Exception:
                pass
        raise RuntimeCycleError("supervision evidence commit failed") from exc

    next_current: Optional[ManagedProcess]
    if supervision.replacement is not None:
        next_current = supervision.replacement
    elif supervision.health_status == "FAILED" and supervision.contained:
        next_current = None
    elif supervision.process_status == "FAILED":
        next_current = None
    else:
        next_current = current

    accepted = {
        "version": heartbeat["version"],
        "sequence": stream["sequence"],
        "observed_at": stream["observed_at"],
    }
    return RuntimeCycleResult(
        supervision=supervision,
        current=next_current,
        accepted_heartbeat=accepted,
        evidence_hash=evidence_hash,
    )
