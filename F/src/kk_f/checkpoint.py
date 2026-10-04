"""F04 durable runtime checkpoint with integrity and monotonic generation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from .input_guard import InputGuardError, read_bounded_text
from .transaction_recovery import TransactionRecoveryError, discard_stale_fixed_temp

from .contracts import RUNTIME_STATUSES

CHECKPOINT_VERSION = "0.1"
CHECKPOINT_FILE = "checkpoint.json"
CHECKPOINT_KEYS = frozenset({"version", "generation", "status", "payload", "checksum"})
HASH_KEYS = ("version", "generation", "status", "payload")


class CheckpointError(ValueError):
    """Raised when checkpoint persistence or verification fails closed."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CheckpointError("checkpoint value is not canonical finite JSON") from exc


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointError("duplicate JSON key")
        result[key] = value
    return result


def _load_json(raw: str) -> dict:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CheckpointError("non-finite number")
            ),
        )
    except CheckpointError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise CheckpointError("invalid checkpoint JSON") from exc
    if not isinstance(value, dict):
        raise CheckpointError("checkpoint object required")
    return value


def _hash_fields(value: dict) -> str:
    material = {key: value[key] for key in HASH_KEYS}
    return hashlib.sha256(_canonical_bytes(material)).hexdigest()


def _validate(value: dict) -> dict:
    if frozenset(value) != CHECKPOINT_KEYS:
        raise CheckpointError("exact checkpoint keys required")
    if value["version"] != CHECKPOINT_VERSION:
        raise CheckpointError("unsupported checkpoint version")
    if type(value["generation"]) is not int or value["generation"] < 0:
        raise CheckpointError("generation must be a non-negative integer")
    if not isinstance(value["status"], str) or value["status"] not in RUNTIME_STATUSES:
        raise CheckpointError("invalid runtime status")
    if not isinstance(value["payload"], dict):
        raise CheckpointError("payload object required")
    _canonical_bytes(value["payload"])
    if not isinstance(value["checksum"], str) or value["checksum"] != _hash_fields(value):
        raise CheckpointError("checkpoint integrity mismatch")
    return value


def checkpoint_checksum(generation: object, status: object, payload: object) -> str:
    """Return the checksum of an otherwise-valid checkpoint record without writing it."""
    if type(generation) is not int or generation < 0:
        raise CheckpointError("generation must be a non-negative integer")
    if not isinstance(status, str) or status not in RUNTIME_STATUSES:
        raise CheckpointError("invalid runtime status")
    if not isinstance(payload, dict):
        raise CheckpointError("payload object required")
    _canonical_bytes(payload)
    record = {
        "version": CHECKPOINT_VERSION,
        "generation": generation,
        "status": status,
        "payload": payload,
        "checksum": "",
    }
    return _hash_fields(record)


def read_checkpoint(directory: str | os.PathLike[str]) -> dict:
    path = Path(directory) / CHECKPOINT_FILE
    if not path.exists():
        raise CheckpointError("checkpoint missing")
    try:
        raw = read_bounded_text(path, max_bytes=65536)
    except InputGuardError as exc:
        raise CheckpointError("checkpoint unreadable or too large") from exc
    result = _validate(_load_json(raw))
    try:
        discard_stale_fixed_temp(path)
    except TransactionRecoveryError as exc:
        raise CheckpointError("checkpoint stale-temp recovery failed") from exc
    return result


def write_checkpoint(
    directory: str | os.PathLike[str],
    generation: object,
    status: object,
    payload: object,
) -> str:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if type(generation) is not int or generation < 0:
        raise CheckpointError("generation must be a non-negative integer")
    if not isinstance(status, str) or status not in RUNTIME_STATUSES:
        raise CheckpointError("invalid runtime status")
    if not isinstance(payload, dict):
        raise CheckpointError("payload object required")
    _canonical_bytes(payload)

    path = root / CHECKPOINT_FILE
    if path.exists():
        existing = read_checkpoint(root)
        if generation <= existing["generation"]:
            raise CheckpointError("checkpoint generation must increase")

    record = {
        "version": CHECKPOINT_VERSION,
        "generation": generation,
        "status": status,
        "payload": payload,
        "checksum": "",
    }
    record["checksum"] = _hash_fields(record)
    data = _canonical_bytes(record) + b"\n"
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        dir_fd = os.open(str(root), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if temp.exists():
            temp.unlink()
    return record["checksum"]
