"""FS07 durable deterministic SAFE_MODE latch around release recovery."""

from __future__ import annotations
import hashlib, json, os, re
from pathlib import Path
from typing import Any
from .input_guard import InputGuardError, read_bounded_text
from .transaction_recovery import TransactionRecoveryError, discard_stale_fixed_temp
from .release_recovery import ReleaseRecoveryError, reconcile_release

VERSION = "0.1"
FILE = "safety-state.json"
MODES = frozenset({"NORMAL", "SAFE_MODE"})
KEYS = frozenset({"version", "generation", "mode", "consecutive_failures", "reason", "checksum"})
HASH_KEYS = ("version", "generation", "mode", "consecutive_failures", "reason")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class SafetyStateError(ValueError):
    pass


def _canonical(v: Any) -> bytes:
    try:
        return json.dumps(
            v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise SafetyStateError("non-canonical safety state") from exc


def _strict(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise SafetyStateError("duplicate JSON key")
        out[k] = v
    return out


def _sum(v: dict) -> str:
    return hashlib.sha256(_canonical({k: v[k] for k in HASH_KEYS})).hexdigest()


def validate_safety_state(v: object) -> dict:
    if not isinstance(v, dict) or frozenset(v) != KEYS:
        raise SafetyStateError("exact safety-state keys required")
    if v["version"] != VERSION:
        raise SafetyStateError("unsupported safety-state version")
    if type(v["generation"]) is not int or v["generation"] < 0:
        raise SafetyStateError("invalid generation")
    if not isinstance(v["mode"], str) or v["mode"] not in MODES:
        raise SafetyStateError("invalid safety mode")
    if type(v["consecutive_failures"]) is not int or v["consecutive_failures"] < 0:
        raise SafetyStateError("invalid failure count")
    if v["mode"] == "NORMAL":
        if v["reason"] is not None:
            raise SafetyStateError("NORMAL reason must be null")
    else:
        if v["reason"] != "RECOVERY_FAILURE_LIMIT" or v["consecutive_failures"] < 1:
            raise SafetyStateError("invalid SAFE_MODE state")
    if (
        not isinstance(v["checksum"], str)
        or _SHA.fullmatch(v["checksum"]) is None
        or v["checksum"] != _sum(v)
    ):
        raise SafetyStateError("safety-state integrity mismatch")
    return dict(v)


def read_safety_state(directory) -> dict:
    p = Path(directory) / FILE
    if not p.exists():
        raise SafetyStateError("safety state missing")
    try:
        v = json.loads(
            read_bounded_text(p, max_bytes=65536),
            object_pairs_hook=_strict,
            parse_constant=lambda _: (_ for _ in ()).throw(SafetyStateError("non-finite number")),
        )
    except SafetyStateError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, InputGuardError) as exc:
        raise SafetyStateError("invalid safety state") from exc
    result = validate_safety_state(v)
    try:
        discard_stale_fixed_temp(p)
    except TransactionRecoveryError as exc:
        raise SafetyStateError("safety-state stale-temp recovery failed") from exc
    return result


def _write(directory, record: dict) -> dict:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    p = root / FILE
    record = dict(record)
    record["checksum"] = _sum(record)
    data = _canonical(record) + b"\n"
    tmp = p.with_name(p.name + ".tmp")
    try:
        with tmp.open("wb") as h:
            h.write(data)
            h.flush()
            os.fsync(h.fileno())
        os.replace(tmp, p)
        fd = os.open(str(root), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SafetyStateError("safety-state commit failed") from exc
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return validate_safety_state(record)


def initialize_safety_state(directory) -> dict:
    p = Path(directory) / FILE
    if p.exists():
        raise SafetyStateError("safety state already exists")
    return _write(
        directory,
        {
            "version": VERSION,
            "generation": 0,
            "mode": "NORMAL",
            "consecutive_failures": 0,
            "reason": None,
            "checksum": "",
        },
    )


def _threshold(v: object) -> int:
    if type(v) is not int or v < 1:
        raise SafetyStateError("failure threshold must be positive integer")
    return v


def _record_failure(directory, threshold: int) -> dict:
    s = read_safety_state(directory)
    if s["mode"] == "SAFE_MODE":
        return s
    n = s["consecutive_failures"] + 1
    mode = "SAFE_MODE" if n >= threshold else "NORMAL"
    reason = "RECOVERY_FAILURE_LIMIT" if mode == "SAFE_MODE" else None
    return _write(
        directory,
        {
            "version": VERSION,
            "generation": s["generation"] + 1,
            "mode": mode,
            "consecutive_failures": n,
            "reason": reason,
            "checksum": "",
        },
    )


def _record_success(directory) -> dict:
    s = read_safety_state(directory)
    if s["mode"] == "SAFE_MODE" or s["consecutive_failures"] == 0:
        return s
    return _write(
        directory,
        {
            "version": VERSION,
            "generation": s["generation"] + 1,
            "mode": "NORMAL",
            "consecutive_failures": 0,
            "reason": None,
            "checksum": "",
        },
    )


def guarded_reconcile(
    safety_dir, store_root, pointer_dir, state_dir, manifests, *, failure_threshold: object
) -> dict:
    threshold = _threshold(failure_threshold)
    s = read_safety_state(safety_dir)
    if s["mode"] == "SAFE_MODE":
        return {"action": "HOLD_SAFE_MODE", "safety": s, "recovery": None}
    try:
        r = reconcile_release(store_root, pointer_dir, state_dir, manifests)
    except ReleaseRecoveryError as exc:
        updated = _record_failure(safety_dir, threshold)
        if updated["mode"] == "SAFE_MODE":
            return {"action": "ENTERED_SAFE_MODE", "safety": updated, "recovery": None}
        raise SafetyStateError("release recovery failed below SAFE_MODE threshold") from exc
    return {"action": "RECOVERY_OK", "safety": _record_success(safety_dir), "recovery": r}


def clear_safe_mode(directory, *, expected_generation: object, acknowledge: object) -> dict:
    s = read_safety_state(directory)
    if s["mode"] != "SAFE_MODE":
        raise SafetyStateError("SAFE_MODE is not latched")
    if type(expected_generation) is not int or expected_generation != s["generation"]:
        raise SafetyStateError("exact current generation acknowledgement required")
    if acknowledge is not True:
        raise SafetyStateError("literal acknowledgement=True required")
    return _write(
        directory,
        {
            "version": VERSION,
            "generation": s["generation"] + 1,
            "mode": "NORMAL",
            "consecutive_failures": 0,
            "reason": None,
            "checksum": "",
        },
    )
