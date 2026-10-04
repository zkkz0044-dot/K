"""FP05/FP06 deterministic local production supervisor entrypoint."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import time
import uuid

from .evidence import EvidenceError, initialize as initialize_evidence, verify as verify_evidence
from .frozen_authority import FrozenAuthorityError, authorize_process
from .health_supervisor import HealthSupervisionResult
from .instance_lock import InstanceLock, InstanceLockError, acquire_instance_lock
from .input_guard import InputGuardError, read_bounded_text, strict_json_loads
from .managed_process import ManagedProcess, ManagedProcessError, launch_managed
from .path_guard import PathGuardError, open_absolute_file, read_all_fd
from .process_preflight import ProcessPreflightError, verify_process_candidate
from .restart_backoff import RestartBackoffError, evaluate_restart_backoff
from .restart_ledger import (
    RestartLedgerError,
    evaluate_and_record,
    initialize,
    read_ledger,
    rollback_pristine_initialization,
)
from .runtime_bootstrap import RuntimeBootstrapError, bootstrap_runtime
from .runtime_cycle import RuntimeCycleError, run_cycle
from .supervision_evidence import SupervisionEvidenceError, record_supervision
from .witness_binding import enabled as witness_enabled

CONFIG_VERSION = "0.1"
CONFIG_KEYS = frozenset(
    {
        "version",
        "authority_path",
        "ledger_directory",
        "evidence_directory",
        "heartbeat_path",
        "process_spec",
        "healthy_within_seconds",
        "degraded_within_seconds",
        "grace_seconds",
        "base_delay_seconds",
        "max_delay_seconds",
        "poll_interval_seconds",
        "heartbeat_startup_grace_seconds",
    }
)


class ProductionDaemonError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    authority_path: str
    ledger_directory: str
    evidence_directory: str
    heartbeat_path: str
    process_spec: dict
    healthy_within_seconds: int
    degraded_within_seconds: int
    grace_seconds: float
    base_delay_seconds: float
    max_delay_seconds: float
    poll_interval_seconds: float
    heartbeat_startup_grace_seconds: float


def _positive_number(value: object, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or value <= 0:
        raise ProductionDaemonError(f"{name} must be a positive number")
    number = float(value)
    if number != number or number == float("inf"):
        raise ProductionDaemonError(f"{name} must be finite")
    return number


def _strict_positive_int(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ProductionDaemonError(f"{name} must be a positive integer")
    return value


def _absolute(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or "\x00" in value
        or len(value) > 4096
    ):
        raise ProductionDaemonError(f"{name} must be a canonical absolute path")
    if value != "/" and (value.endswith("/") or "//" in value):
        raise ProductionDaemonError(f"{name} must be a canonical absolute path")
    p = PurePosixPath(value)
    if (
        not p.parts
        or p.parts[0] != "/"
        or any(part in ("", ".", "..") for part in p.parts[1:])
        or p.as_posix() != value
    ):
        raise ProductionDaemonError(f"{name} must be a canonical absolute path")
    return value


def load_runtime_config(path: str) -> RuntimeConfig:
    config_value = _absolute(path, "config path")
    fd = -1
    try:
        fd = open_absolute_file(config_value)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ProductionDaemonError("runtime config must be a regular file")
        if info.st_uid != 0:
            raise ProductionDaemonError("runtime config must be root-owned")
        if info.st_mode & 0o022:
            raise ProductionDaemonError("runtime config must not be group/world writable")
        raw_bytes = read_all_fd(fd, max_bytes=1024 * 1024)
        try:
            raw = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProductionDaemonError("runtime config unreadable or invalid") from exc
        value = strict_json_loads(raw, max_chars=1024 * 1024)
    except ProductionDaemonError:
        raise
    except (PathGuardError, OSError, json.JSONDecodeError, InputGuardError) as exc:
        raise ProductionDaemonError("runtime config unreadable or invalid") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(value, dict) or frozenset(value) != CONFIG_KEYS:
        raise ProductionDaemonError("runtime config exact keys required")
    if value["version"] != CONFIG_VERSION:
        raise ProductionDaemonError("unsupported runtime config version")
    healthy = _strict_positive_int(value["healthy_within_seconds"], "healthy_within_seconds")
    degraded = _strict_positive_int(value["degraded_within_seconds"], "degraded_within_seconds")
    if degraded < healthy:
        raise ProductionDaemonError("degraded threshold must be >= healthy threshold")
    return RuntimeConfig(
        authority_path=_absolute(value["authority_path"], "authority_path"),
        ledger_directory=_absolute(value["ledger_directory"], "ledger_directory"),
        evidence_directory=_absolute(value["evidence_directory"], "evidence_directory"),
        heartbeat_path=_absolute(value["heartbeat_path"], "heartbeat_path"),
        process_spec=value["process_spec"],
        healthy_within_seconds=healthy,
        degraded_within_seconds=degraded,
        grace_seconds=_positive_number(value["grace_seconds"], "grace_seconds"),
        base_delay_seconds=_positive_number(value["base_delay_seconds"], "base_delay_seconds"),
        max_delay_seconds=_positive_number(value["max_delay_seconds"], "max_delay_seconds"),
        poll_interval_seconds=_positive_number(
            value["poll_interval_seconds"], "poll_interval_seconds"
        ),
        heartbeat_startup_grace_seconds=_positive_number(
            value["heartbeat_startup_grace_seconds"], "heartbeat_startup_grace_seconds"
        ),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _message_id(authority_id: str, generation: int, timestamp: str, decision: str) -> str:
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"kk-f:{authority_id}:{generation}:{timestamp}:{decision}")
    )


def _load_heartbeat(path: str) -> dict | None:
    try:
        if not Path(path).exists():
            return None
        raw = read_bounded_text(path, max_bytes=65536)
        value = strict_json_loads(raw, max_chars=65536)
    except InputGuardError as exc:
        raise ProductionDaemonError("heartbeat read/JSON invalid") from exc
    if not isinstance(value, dict):
        raise ProductionDaemonError("heartbeat must be an object")
    return value


def _ensure_evidence(directory: str) -> None:
    root = Path(directory)
    if root.exists():
        try:
            verify_evidence(directory)
        except EvidenceError as exc:
            raise ProductionDaemonError("existing evidence store invalid") from exc
    else:
        try:
            initialize_evidence(directory)
        except EvidenceError as exc:
            raise ProductionDaemonError("evidence initialization failed") from exc


def _record_recovery(
    cfg: RuntimeConfig,
    authority_id: str,
    result: HealthSupervisionResult,
    generation: int,
    timestamp: str,
) -> None:
    try:
        record_supervision(
            cfg.evidence_directory,
            result,
            message_id=_message_id(authority_id, generation, timestamp, result.decision),
            timestamp=timestamp,
        )
    except SupervisionEvidenceError as exc:
        if result.replacement is not None:
            try:
                result.replacement.stop(grace_seconds=cfg.grace_seconds)
            except Exception:
                pass
        raise ProductionDaemonError("recovery evidence commit failed") from exc


def _recover_absent(cfg: RuntimeConfig, authority_id: str, now: str) -> ManagedProcess | None:
    try:
        authorization = authorize_process(cfg.authority_path, cfg.process_spec)
        verify_process_candidate(cfg.process_spec)
        ledger = read_ledger(cfg.ledger_directory)
    except (FrozenAuthorityError, ProcessPreflightError, RestartLedgerError) as exc:
        raise ProductionDaemonError("recovery authorization/state invalid") from exc
    if ledger["max_attempts"] != authorization["max_restart_attempts"]:
        raise ProductionDaemonError("recovery budget mismatch")
    if ledger["attempts"] >= ledger["max_attempts"]:
        if ledger["last_decision"] == "HOLD_FAILED":
            return None
        held = evaluate_and_record(cfg.ledger_directory, "FAILED")
        result = HealthSupervisionResult(
            "FAILED", "FAILED", held["last_decision"], held["attempts"], False, None
        )
        _record_recovery(cfg, authority_id, result, held["generation"], now)
        return None
    try:
        backoff = evaluate_restart_backoff(
            ledger,
            now=now,
            base_delay_seconds=cfg.base_delay_seconds,
            max_delay_seconds=cfg.max_delay_seconds,
        )
    except RestartBackoffError as exc:
        raise ProductionDaemonError("recovery backoff invalid") from exc
    if not backoff["allowed"]:
        return None
    try:
        committed = evaluate_and_record(cfg.ledger_directory, "FAILED", attempted_at=now)
        try:
            Path(cfg.heartbeat_path).unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ProductionDaemonError("stale heartbeat cleanup failed") from exc
        replacement = launch_managed(cfg.process_spec)
    except RestartLedgerError as exc:
        raise ProductionDaemonError("recovery attempt commit failed") from exc
    except ManagedProcessError as exc:
        raise ProductionDaemonError("replacement launch failed after durable attempt") from exc
    result = HealthSupervisionResult(
        "FAILED", "FAILED", "REPLACE_INSTANCE", committed["attempts"], False, replacement
    )
    _record_recovery(cfg, authority_id, result, committed["generation"], now)
    return replacement


def run_daemon(config_path: str, *, stop_after_cycles: int | None = None) -> int:
    cfg = load_runtime_config(config_path)
    try:
        authorization = authorize_process(cfg.authority_path, cfg.process_spec)
        verify_process_candidate(cfg.process_spec)
    except (FrozenAuthorityError, ProcessPreflightError) as exc:
        raise ProductionDaemonError("initial authorization/preflight failed") from exc
    _ensure_evidence(cfg.evidence_directory)

    stop_requested = False

    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    old_term = signal.signal(signal.SIGTERM, request_stop)
    old_int = signal.signal(signal.SIGINT, request_stop)

    worker: ManagedProcess | None = None
    instance_lock: InstanceLock | None = None
    previous_heartbeat = None
    worker_started_monotonic = 0.0
    cycles = 0
    try:
        ledger_path = Path(cfg.ledger_directory) / "checkpoint.json"
        if not ledger_path.exists():
            try:
                try:
                    Path(cfg.heartbeat_path).unlink()
                except FileNotFoundError:
                    pass
                boot = bootstrap_runtime(cfg.authority_path, cfg.ledger_directory, cfg.process_spec)
            except RuntimeBootstrapError as exc:
                raise ProductionDaemonError("initial bootstrap failed") from exc
            worker = boot.worker
            instance_lock = boot.instance_lock
            worker_started_monotonic = time.monotonic()
        else:
            lock_path = str(
                Path(cfg.ledger_directory).with_name(Path(cfg.ledger_directory).name + ".lock")
            )
            try:
                instance_lock = acquire_instance_lock(lock_path)
                read_ledger(cfg.ledger_directory)
            except (InstanceLockError, RestartLedgerError) as exc:
                raise ProductionDaemonError("resume lock/ledger validation failed") from exc

        while not stop_requested:
            if worker is None:
                now = _now()
                worker = _recover_absent(cfg, authorization["authority_id"], now)
                if worker is not None:
                    previous_heartbeat = None
                    worker_started_monotonic = time.monotonic()
                time.sleep(cfg.poll_interval_seconds)
                cycles += 1
                if stop_after_cycles is not None and cycles >= stop_after_cycles:
                    break
                continue

            observed = worker.observe()
            if observed["status"] != "RUNNING":
                worker = None
                continue

            heartbeat = _load_heartbeat(cfg.heartbeat_path)
            if heartbeat is None:
                if (
                    time.monotonic() - worker_started_monotonic
                    > cfg.heartbeat_startup_grace_seconds
                ):
                    try:
                        worker.stop(grace_seconds=cfg.grace_seconds)
                    except ManagedProcessError as exc:
                        raise ProductionDaemonError(
                            "heartbeat startup timeout containment failed"
                        ) from exc
                    worker = None
                time.sleep(cfg.poll_interval_seconds)
                cycles += 1
                if stop_after_cycles is not None and cycles >= stop_after_cycles:
                    break
                continue

            # Capture supervision time only after reading the heartbeat. A worker may
            # atomically publish a new heartbeat between iterations; using a timestamp
            # captured before that read can falsely classify valid evidence as future.
            now = _now()
            try:
                cycle = run_cycle(
                    cfg.authority_path,
                    cfg.ledger_directory,
                    cfg.evidence_directory,
                    worker,
                    heartbeat,
                    cfg.process_spec,
                    previous_heartbeat=previous_heartbeat,
                    now=now,
                    healthy_within_seconds=cfg.healthy_within_seconds,
                    degraded_within_seconds=cfg.degraded_within_seconds,
                    grace_seconds=cfg.grace_seconds,
                    message_id=_message_id(
                        authorization["authority_id"],
                        read_ledger(cfg.ledger_directory)["generation"],
                        now,
                        "cycle",
                    ),
                    timestamp=now,
                    base_delay_seconds=cfg.base_delay_seconds,
                    max_delay_seconds=cfg.max_delay_seconds,
                    _allow_identical_poll_snapshot=True,
                )
            except (RuntimeCycleError, RestartLedgerError) as exc:
                raise ProductionDaemonError("runtime cycle failed closed") from exc
            worker = cycle.current
            if worker is not None and cycle.supervision.replacement is not None:
                try:
                    Path(cfg.heartbeat_path).unlink()
                except FileNotFoundError:
                    pass
                previous_heartbeat = None
                worker_started_monotonic = time.monotonic()
            else:
                previous_heartbeat = cycle.accepted_heartbeat if worker is not None else None
            time.sleep(cfg.poll_interval_seconds)
            cycles += 1
            if stop_after_cycles is not None and cycles >= stop_after_cycles:
                break
        return 0
    finally:
        if worker is not None:
            try:
                worker.stop(grace_seconds=cfg.grace_seconds)
            except Exception:
                pass
        if instance_lock is not None:
            try:
                try:
                    ledger = read_ledger(cfg.ledger_directory)
                    if (
                        (not witness_enabled())
                        and ledger["generation"] == 0
                        and ledger["attempts"] == 0
                        and ledger["last_decision"] == "NO_ACTION"
                    ):
                        rollback_pristine_initialization(
                            cfg.ledger_directory, ledger["max_attempts"]
                        )
                except RestartLedgerError:
                    pass
                instance_lock.release()
            except Exception:
                pass
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--stop-after-cycles", type=int)
    args = parser.parse_args(argv)
    return run_daemon(args.config, stop_after_cycles=args.stop_after_cycles)


if __name__ == "__main__":
    raise SystemExit(main())
