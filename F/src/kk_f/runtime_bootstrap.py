"""F19 Frozen-Authority runtime bootstrap for an initial managed worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .frozen_authority import FrozenAuthorityError, authorize_process
from .instance_lock import InstanceLock, InstanceLockError, acquire_instance_lock
from .managed_process import ManagedProcess, ManagedProcessError, launch_managed
from .process_preflight import ProcessPreflightError, verify_process_candidate
from .witness_binding import enabled as witness_enabled
from .restart_ledger import (
    RestartLedgerError,
    initialize as initialize_restart_ledger,
    read_ledger,
    rollback_pristine_initialization,
)


class RuntimeBootstrapError(RuntimeError):
    """Raised when F19 cannot safely bootstrap an authorized local runtime."""


@dataclass(frozen=True)
class RuntimeBootstrapResult:
    authority_id: str
    max_restart_attempts: int
    worker: ManagedProcess
    instance_lock: InstanceLock


def _default_lock_path(ledger_directory: str) -> str:
    ledger = Path(ledger_directory)
    if not ledger.is_absolute():
        raise RuntimeBootstrapError("ledger directory must be absolute")
    return str(ledger.with_name(ledger.name + ".lock"))


def _is_pristine_ledger(ledger: dict, maximum: int) -> bool:
    return ledger == {
        "generation": 0,
        "status": "READY",
        "ledger_version": "0.2",
        "attempts": 0,
        "max_attempts": maximum,
        "last_decision": "NO_ACTION",
        "last_attempt_at": None,
    }


def bootstrap_runtime(
    authority_path: str,
    ledger_directory: str,
    process_spec: object,
    *,
    lock_path: str | None = None,
) -> RuntimeBootstrapResult:
    try:
        authorization = authorize_process(authority_path, process_spec)
    except FrozenAuthorityError as exc:
        raise RuntimeBootstrapError("Frozen Authority denied runtime candidate") from exc

    try:
        verify_process_candidate(process_spec)
    except ProcessPreflightError as exc:
        raise RuntimeBootstrapError(
            "authorized candidate failed preflight before runtime mutation"
        ) from exc

    resolved_lock_path = _default_lock_path(ledger_directory) if lock_path is None else lock_path
    try:
        instance_lock = acquire_instance_lock(resolved_lock_path)
    except InstanceLockError as exc:
        raise RuntimeBootstrapError("single-instance lock acquisition failed") from exc

    try:
        ledger_path = Path(ledger_directory) / "checkpoint.json"
        if ledger_path.exists():
            try:
                existing = read_ledger(ledger_directory)
            except RestartLedgerError as exc:
                raise RuntimeBootstrapError(
                    "existing restart ledger is invalid; refusing reset"
                ) from exc
            if not _is_pristine_ledger(existing, authorization["max_restart_attempts"]):
                raise RuntimeBootstrapError("existing non-pristine restart ledger blocks bootstrap")
            if not witness_enabled():
                try:
                    rollback_pristine_initialization(
                        ledger_directory, authorization["max_restart_attempts"]
                    )
                except RestartLedgerError as exc:
                    raise RuntimeBootstrapError(
                        "abandoned pristine ledger recovery failed"
                    ) from exc

        if not ledger_path.exists():
            try:
                initialize_restart_ledger(ledger_directory, authorization["max_restart_attempts"])
            except RestartLedgerError as exc:
                raise RuntimeBootstrapError("restart ledger initialization failed") from exc

        try:
            worker = launch_managed(process_spec)
        except ManagedProcessError as exc:
            cause = exc.__cause__
            if isinstance(cause, OSError):
                if not witness_enabled():
                    try:
                        rollback_pristine_initialization(
                            ledger_directory, authorization["max_restart_attempts"]
                        )
                    except RestartLedgerError as rollback_exc:
                        raise RuntimeBootstrapError(
                            "worker spawn failed and pristine-ledger rollback failed closed"
                        ) from rollback_exc
                    raise RuntimeBootstrapError(
                        "worker spawn failed; pristine bootstrap ledger rolled back for retry"
                    ) from exc
                raise RuntimeBootstrapError(
                    "worker spawn failed; witness-bound pristine ledger retained for retry"
                ) from exc
            raise RuntimeBootstrapError(
                "authorized worker launch failed after ledger initialization"
            ) from exc

        return RuntimeBootstrapResult(
            authority_id=authorization["authority_id"],
            max_restart_attempts=authorization["max_restart_attempts"],
            worker=worker,
            instance_lock=instance_lock,
        )
    except Exception:
        instance_lock.release()
        raise
