"""FP04 isolated runtime self-test. Never operates on production paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .evidence import EvidenceError, initialize as initialize_evidence, verify as verify_evidence
from .runtime_bootstrap import RuntimeBootstrapError, bootstrap_runtime
from .runtime_cycle import RuntimeCycleError, run_cycle


class SelfTestError(RuntimeError):
    """Raised when the isolated self-test cannot be completed safely."""


@dataclass(frozen=True)
class SelfTestResult:
    worker_pid: int
    health_status: str
    evidence_count: int
    evidence_hash: str


def _inside(root: Path, candidate: str) -> Path:
    value = Path(candidate)
    if not value.is_absolute():
        raise SelfTestError("self-test paths must be absolute")
    try:
        resolved = value.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise SelfTestError("self-test path escapes isolation root") from exc
    return resolved


def run_isolated_self_test(
    isolation_root: str,
    authority_path: str,
    ledger_directory: str,
    evidence_directory: str,
    process_spec: object,
    *,
    now: str,
) -> SelfTestResult:
    root = Path(isolation_root)
    if not root.is_absolute():
        raise SelfTestError("isolation root must be absolute")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise SelfTestError("isolation root must be a directory")

    authority = _inside(root, authority_path)
    ledger = _inside(root, ledger_directory)
    evidence = _inside(root, evidence_directory)
    if not isinstance(process_spec, dict):
        raise SelfTestError("process spec must be an object")
    executable = _inside(root, process_spec.get("executable", ""))
    cwd = _inside(root, process_spec.get("cwd", ""))
    if authority == executable:
        raise SelfTestError("self-test authority must be distinct from executable")
    if ledger == evidence or cwd == evidence:
        raise SelfTestError("self-test mutable paths must be distinct")
    if ledger.exists() or evidence.exists():
        raise SelfTestError("self-test ledger/evidence paths must start absent")

    try:
        initialize_evidence(str(evidence))
    except EvidenceError as exc:
        raise SelfTestError("isolated evidence initialization failed") from exc

    boot = None
    try:
        try:
            boot = bootstrap_runtime(str(authority), str(ledger), process_spec)
        except RuntimeBootstrapError as exc:
            raise SelfTestError("isolated bootstrap failed") from exc

        heartbeat = {"version": "0.1", "sequence": 1, "observed_at": now}
        try:
            cycle = run_cycle(
                str(authority),
                str(ledger),
                str(evidence),
                boot.worker,
                heartbeat,
                process_spec,
                previous_heartbeat=None,
                now=now,
                healthy_within_seconds=15,
                degraded_within_seconds=30,
                grace_seconds=0.1,
                message_id="123e4567-e89b-42d3-a456-4266141740aa",
                timestamp=now,
            )
        except RuntimeCycleError as exc:
            raise SelfTestError("isolated runtime cycle failed") from exc
        verified = verify_evidence(str(evidence))
        return SelfTestResult(
            worker_pid=boot.worker.pid,
            health_status=cycle.supervision.health_status,
            evidence_count=verified["count"],
            evidence_hash=cycle.evidence_hash,
        )
    finally:
        if boot is not None:
            try:
                boot.worker.stop(grace_seconds=0.1)
            finally:
                boot.instance_lock.release()
