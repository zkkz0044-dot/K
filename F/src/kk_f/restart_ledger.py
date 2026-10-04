"""F08 durable bounded restart ledger built on F04 checkpointing."""

from __future__ import annotations

import os
from pathlib import Path

from .checkpoint import CheckpointError, checkpoint_checksum, read_checkpoint, write_checkpoint
from .heartbeat import HeartbeatError, _parse_rfc3339
from .restart_policy import DECISIONS, RestartPolicyError, decide
from .witness_binding import (
    WitnessBindingError,
    commit_transition,
    enabled as witness_enabled,
    prepare_transition,
    recover_current,
    verify_baseline,
)

LEDGER_VERSION = "0.2"
LEDGER_KEYS = frozenset(
    {"ledger_version", "attempts", "max_attempts", "last_decision", "last_attempt_at"}
)


class RestartLedgerError(ValueError):
    """Raised when durable restart accounting violates the F08 contract."""


def _strict_int(value: object, where: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise RestartLedgerError(f"{where}: integer >= {minimum} required")
    return value


def _validate_payload(payload: object) -> dict:
    if not isinstance(payload, dict) or frozenset(payload) != LEDGER_KEYS:
        raise RestartLedgerError("ledger payload: exact keys required")
    if payload["ledger_version"] != LEDGER_VERSION:
        raise RestartLedgerError("ledger payload: unsupported version")
    attempts = _strict_int(payload["attempts"], "attempts")
    maximum = _strict_int(payload["max_attempts"], "max_attempts", 1)
    if attempts > maximum:
        raise RestartLedgerError("attempts cannot exceed max_attempts")
    if payload["last_decision"] not in DECISIONS:
        raise RestartLedgerError("invalid last_decision")
    attempted_at = payload["last_attempt_at"]
    if attempted_at is not None:
        try:
            _parse_rfc3339(attempted_at, "last_attempt_at")
        except HeartbeatError as exc:
            raise RestartLedgerError("invalid last_attempt_at") from exc
    return payload


def initialize(directory: str, max_attempts: object) -> dict:
    maximum = _strict_int(max_attempts, "max_attempts", 1)
    payload = {
        "ledger_version": LEDGER_VERSION,
        "attempts": 0,
        "max_attempts": maximum,
        "last_decision": "NO_ACTION",
        "last_attempt_at": None,
    }
    expected_digest = checkpoint_checksum(0, "READY", payload)
    try:
        verify_baseline("restart_ledger", 0, expected_digest)
        written = write_checkpoint(directory, 0, "READY", payload)
        if written != expected_digest:
            raise RestartLedgerError("ledger initialization digest mismatch")
        recover_current("restart_ledger", 0, expected_digest)
    except (CheckpointError, OSError, WitnessBindingError) as exc:
        raise RestartLedgerError("ledger initialization failed") from exc
    return {"generation": 0, "status": "READY", **payload}


def _read_ledger_checkpoint(directory: str) -> tuple[dict, dict]:
    try:
        checkpoint = read_checkpoint(directory)
        payload = _validate_payload(checkpoint["payload"])
        recover_current("restart_ledger", checkpoint["generation"], checkpoint["checksum"])
    except (CheckpointError, OSError, WitnessBindingError) as exc:
        raise RestartLedgerError("ledger checkpoint invalid") from exc
    ledger = {"generation": checkpoint["generation"], "status": checkpoint["status"], **payload}
    return ledger, checkpoint


def read_ledger(directory: str) -> dict:
    ledger, _ = _read_ledger_checkpoint(directory)
    return ledger


def rollback_pristine_initialization(directory: str, max_attempts: object) -> None:
    """Remove only the exact generation-0 ledger created by a failed bootstrap.

    Any ambiguity or mutation fails closed and preserves the ledger.
    """
    maximum = _strict_int(max_attempts, "max_attempts", 1)
    ledger = read_ledger(directory)
    expected = {
        "generation": 0,
        "status": "READY",
        "ledger_version": LEDGER_VERSION,
        "attempts": 0,
        "max_attempts": maximum,
        "last_decision": "NO_ACTION",
        "last_attempt_at": None,
    }
    if ledger != expected:
        raise RestartLedgerError("bootstrap rollback requires exact pristine ledger")
    if witness_enabled():
        # A witness-bound pristine baseline is durable authority and is intentionally
        # retained for a subsequent bootstrap retry rather than deleted.
        return

    root = Path(directory)
    checkpoint = root / "checkpoint.json"
    try:
        checkpoint.unlink()
        dir_fd = os.open(str(root), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        try:
            root.rmdir()
        except OSError:
            pass
    except OSError as exc:
        raise RestartLedgerError("bootstrap rollback failed") from exc


def evaluate_and_record(
    directory: str, runtime_status: object, *, attempted_at: object = None
) -> dict:
    ledger, current_checkpoint = _read_ledger_checkpoint(directory)
    try:
        outcome = decide(runtime_status, ledger["attempts"], ledger["max_attempts"])
    except RestartPolicyError as exc:
        raise RestartLedgerError("restart decision failed") from exc

    attempts = ledger["attempts"]
    last_attempt_at = ledger["last_attempt_at"]
    if outcome["decision"] == "REPLACE_INSTANCE":
        attempts += 1
        if attempted_at is not None:
            try:
                _parse_rfc3339(attempted_at, "attempted_at")
            except HeartbeatError as exc:
                raise RestartLedgerError("attempted_at invalid") from exc
            last_attempt_at = attempted_at
    elif attempted_at is not None:
        raise RestartLedgerError("attempted_at allowed only for replacement attempt")
    payload = {
        "ledger_version": LEDGER_VERSION,
        "attempts": attempts,
        "max_attempts": ledger["max_attempts"],
        "last_decision": outcome["decision"],
        "last_attempt_at": last_attempt_at,
    }
    generation = ledger["generation"] + 1
    new_digest = checkpoint_checksum(generation, runtime_status, payload)
    try:
        prepare_transition(
            "restart_ledger",
            ledger["generation"],
            current_checkpoint["checksum"],
            generation,
            new_digest,
        )
        written = write_checkpoint(directory, generation, runtime_status, payload)
        if written != new_digest:
            raise RestartLedgerError("ledger commit digest mismatch")
        commit_transition("restart_ledger", generation, new_digest)
    except (CheckpointError, OSError, WitnessBindingError) as exc:
        raise RestartLedgerError("ledger commit failed") from exc
    return {"generation": generation, "status": runtime_status, **payload}
