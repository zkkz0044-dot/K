"""F02 deterministic evidence log with fail-closed audit verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from .contracts import ContractError, validate_message
from .input_guard import InputGuardError, read_bounded_text
from .transaction_recovery import TransactionRecoveryError, discard_stale_fixed_temp
from .witness_binding import (
    WitnessBindingError,
    commit_transition,
    enabled as witness_enabled,
    prepare_transition,
    recover_current,
    verify_baseline,
)

EVIDENCE_VERSION = "0.1"
GENESIS_HASH = "0" * 64
ENTRY_KEYS = frozenset({"seq", "prev_hash", "record", "record_hash"})
HEAD_KEYS = frozenset({"version", "count", "last_hash"})
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_HEAD_BYTES = 65536
MAX_ENTRY_BYTES = 1024 * 1024


class EvidenceError(ValueError):
    """Raised when evidence storage or verification violates the F02 contract."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceError("value is not canonical JSON") from exc
    return text.encode("utf-8")


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json(raw: str, where: str) -> dict:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=lambda x: (_ for _ in ()).throw(
                EvidenceError(f"non-finite number: {x}")
            ),
        )
    except EvidenceError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise EvidenceError(f"{where}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{where}: object required")
    return value


def _exact_keys(value: dict, expected: frozenset[str], where: str) -> None:
    if frozenset(value) != expected:
        raise EvidenceError(f"{where}: exact keys required")


def _hash_record(seq: int, prev_hash: str, record: dict) -> str:
    material = {"seq": seq, "prev_hash": prev_hash, "record": record}
    return hashlib.sha256(_canonical_bytes(material)).hexdigest()


def _validate_record(record: object) -> dict:
    if not isinstance(record, dict):
        raise EvidenceError("record: object required")
    try:
        validate_message(record)
    except ContractError as exc:
        raise EvidenceError("record: invalid F01 message") from exc
    _canonical_bytes(record)
    return record


def _validate_head(head: dict) -> None:
    _exact_keys(head, HEAD_KEYS, "head")
    if head["version"] != EVIDENCE_VERSION:
        raise EvidenceError("head: unsupported version")
    if type(head["count"]) is not int or head["count"] < 0:
        raise EvidenceError("head.count: non-negative integer required")
    if not isinstance(head["last_hash"], str) or not HEX64_RE.fullmatch(head["last_hash"]):
        raise EvidenceError("head.last_hash: lowercase SHA-256 required")


def _paths(directory: Path) -> tuple[Path, Path]:
    return directory / "evidence.jsonl", directory / "HEAD.json"


def _read_head(path: Path) -> dict:
    if not path.exists():
        raise EvidenceError("HEAD missing")
    try:
        raw = read_bounded_text(path, max_bytes=MAX_HEAD_BYTES)
    except InputGuardError as exc:
        raise EvidenceError("HEAD unreadable or too large") from exc
    head = _load_json(raw, "head")
    _validate_head(head)
    return head


def _atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def initialize(directory: str | os.PathLike[str]) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    log_path, head_path = _paths(root)
    if log_path.exists() or head_path.exists():
        raise EvidenceError("evidence store already exists")
    try:
        verify_baseline("evidence", 0, GENESIS_HASH)
    except WitnessBindingError as exc:
        raise EvidenceError("evidence witness baseline mismatch") from exc
    _atomic_write(log_path, b"")
    head = {"version": EVIDENCE_VERSION, "count": 0, "last_hash": GENESIS_HASH}
    _atomic_write(head_path, _canonical_bytes(head) + b"\n")


def _scan_log(log_path: Path, head: dict | None = None) -> tuple[int, str, bool]:
    if not log_path.exists():
        raise EvidenceError("evidence log missing")
    expected_seq = 1
    prev_hash = GENESIS_HASH
    head_matched = head is not None and head["count"] == 0 and head["last_hash"] == GENESIS_HASH
    try:
        with log_path.open("rb") as handle:
            while True:
                raw = handle.readline(MAX_ENTRY_BYTES + 1)
                if not raw:
                    break
                if len(raw) > MAX_ENTRY_BYTES:
                    raise EvidenceError("evidence log entry exceeds size limit")
                if not raw.endswith(b"\n"):
                    raise EvidenceError("evidence log entry must be newline terminated")
                if raw == b"\n":
                    raise EvidenceError("evidence log: blank line forbidden")
                try:
                    line = raw[:-1].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise EvidenceError("evidence log: invalid UTF-8") from exc
                entry = _load_json(line, f"entry {expected_seq}")
                _exact_keys(entry, ENTRY_KEYS, f"entry {expected_seq}")
                if type(entry["seq"]) is not int or entry["seq"] != expected_seq:
                    raise EvidenceError("entry sequence mismatch")
                if entry["prev_hash"] != prev_hash:
                    raise EvidenceError("previous hash mismatch")
                _validate_record(entry["record"])
                actual_hash = _hash_record(entry["seq"], entry["prev_hash"], entry["record"])
                if not isinstance(entry["record_hash"], str) or entry["record_hash"] != actual_hash:
                    raise EvidenceError("record hash mismatch")
                prev_hash = actual_hash
                if (
                    head is not None
                    and expected_seq == head["count"]
                    and prev_hash == head["last_hash"]
                ):
                    head_matched = True
                expected_seq += 1
    except EvidenceError:
        raise
    except OSError as exc:
        raise EvidenceError("evidence log read failed") from exc
    return expected_seq - 1, prev_hash, head_matched


def append(directory: str | os.PathLike[str], record: object) -> str:
    root = Path(directory)
    log_path, head_path = _paths(root)
    verified = verify(root)
    record = _validate_record(record)
    seq = verified["count"] + 1
    prev_hash = verified["last_hash"]
    record_hash = _hash_record(seq, prev_hash, record)
    entry = {"seq": seq, "prev_hash": prev_hash, "record": record, "record_hash": record_hash}
    line = _canonical_bytes(entry) + b"\n"
    try:
        prepare_transition("evidence", verified["count"], verified["last_hash"], seq, record_hash)
        with log_path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        head = {"version": EVIDENCE_VERSION, "count": seq, "last_hash": record_hash}
        _atomic_write(head_path, _canonical_bytes(head) + b"\n")
        commit_transition("evidence", seq, record_hash)
    except WitnessBindingError as exc:
        raise EvidenceError("evidence witness transition failed") from exc
    return record_hash


def verify(directory: str | os.PathLike[str]) -> dict:
    root = Path(directory)
    log_path, head_path = _paths(root)
    head = _read_head(head_path) if head_path.exists() else None
    count, last_hash, head_matched = _scan_log(log_path, head)

    if witness_enabled():
        try:
            recover_current("evidence", count, last_hash)
        except WitnessBindingError as exc:
            raise EvidenceError("evidence rollback/replay rejected by witness") from exc
        if head is None or head["count"] != count or head["last_hash"] != last_hash:
            if head is not None and (head["count"] > count or not head_matched):
                raise EvidenceError("HEAD is not a valid prefix of witnessed evidence log")
            repaired = {"version": EVIDENCE_VERSION, "count": count, "last_hash": last_hash}
            _atomic_write(head_path, _canonical_bytes(repaired) + b"\n")
        try:
            discard_stale_fixed_temp(head_path)
        except TransactionRecoveryError as exc:
            raise EvidenceError("HEAD stale-temp recovery failed") from exc
        return {"version": EVIDENCE_VERSION, "count": count, "last_hash": last_hash}

    if head is None:
        raise EvidenceError("HEAD missing")
    if head["count"] != count or head["last_hash"] != last_hash:
        raise EvidenceError("HEAD/log mismatch; truncation or incomplete commit detected")
    try:
        discard_stale_fixed_temp(head_path)
    except TransactionRecoveryError as exc:
        raise EvidenceError("HEAD stale-temp recovery failed") from exc
    return {"version": EVIDENCE_VERSION, "count": count, "last_hash": last_hash}
