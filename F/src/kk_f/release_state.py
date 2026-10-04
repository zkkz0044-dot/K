"""FS03 durable authoritative ACTIVE/CANDIDATE/LKG release identity state."""

from __future__ import annotations
import hashlib, json, os, re, uuid
from pathlib import Path
from typing import Any
from .input_guard import InputGuardError, read_bounded_text
from .transaction_recovery import TransactionRecoveryError, discard_stale_fixed_temp

STATE_VERSION = "0.1"
STATE_FILE = "release-state.json"
STATE_KEYS = frozenset(
    {"version", "generation", "active", "candidate", "last_known_good", "checksum"}
)
IDENTITY_KEYS = frozenset({"release_id", "manifest_sha256"})
HASH_KEYS = ("version", "generation", "active", "candidate", "last_known_good")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReleaseStateError(ValueError):
    """Raised when release role state is invalid, corrupt, or cannot commit safely."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReleaseStateError("state is not canonical finite JSON") from exc


def _strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReleaseStateError("duplicate JSON key")
        out[key] = value
    return out


def _identity(value: object, *, nullable: bool = False):
    if value is None and nullable:
        return None
    if not isinstance(value, dict) or frozenset(value) != IDENTITY_KEYS:
        raise ReleaseStateError("exact release identity required")
    rid, digest = value["release_id"], value["manifest_sha256"]
    if not isinstance(rid, str):
        raise ReleaseStateError("release_id string required")
    try:
        parsed = uuid.UUID(rid)
    except (ValueError, AttributeError) as exc:
        raise ReleaseStateError("invalid release_id") from exc
    if str(parsed) != rid:
        raise ReleaseStateError("release_id must be canonical lowercase UUID")
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        raise ReleaseStateError("manifest_sha256 must be lowercase 64-hex")
    return {"release_id": rid, "manifest_sha256": digest}


def _checksum(value: dict) -> str:
    return hashlib.sha256(_canonical({key: value[key] for key in HASH_KEYS})).hexdigest()


def validate_release_state(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != STATE_KEYS:
        raise ReleaseStateError("exact state keys required")
    if value["version"] != STATE_VERSION:
        raise ReleaseStateError("unsupported state version")
    if type(value["generation"]) is not int or value["generation"] < 0:
        raise ReleaseStateError("generation must be non-negative integer")
    active = _identity(value["active"])
    candidate = _identity(value["candidate"], nullable=True)
    lkg = _identity(value["last_known_good"])
    if candidate is not None and candidate == active:
        raise ReleaseStateError("candidate cannot equal active")
    checksum = value["checksum"]
    if (
        not isinstance(checksum, str)
        or _SHA256_RE.fullmatch(checksum) is None
        or checksum != _checksum(value)
    ):
        raise ReleaseStateError("release state integrity mismatch")
    return {
        "version": STATE_VERSION,
        "generation": value["generation"],
        "active": active,
        "candidate": candidate,
        "last_known_good": lkg,
        "checksum": checksum,
    }


def read_release_state(directory: str | os.PathLike[str]) -> dict:
    path = Path(directory) / STATE_FILE
    if not path.exists():
        raise ReleaseStateError("release state missing")
    try:
        raw = read_bounded_text(path, max_bytes=65536)
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ReleaseStateError("non-finite number")),
        )
    except ReleaseStateError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, OSError, TypeError, InputGuardError) as exc:
        raise ReleaseStateError("invalid release state") from exc
    result = validate_release_state(value)
    try:
        discard_stale_fixed_temp(path)
    except TransactionRecoveryError as exc:
        raise ReleaseStateError("release-state stale-temp recovery failed") from exc
    return result


def _write(directory: str | os.PathLike[str], record: dict) -> dict:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    path = root / STATE_FILE
    record = dict(record)
    record["checksum"] = _checksum(record)
    data = _canonical(record) + b"\n"
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("wb") as h:
            h.write(data)
            h.flush()
            os.fsync(h.fileno())
        os.replace(temp, path)
        dfd = os.open(str(root), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError as exc:
        raise ReleaseStateError("release state commit failed") from exc
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
    return validate_release_state(record)


def initialize_release_state(directory, active_identity: object) -> dict:
    root = Path(directory)
    path = root / STATE_FILE
    if path.exists():
        raise ReleaseStateError("release state already exists")
    active = _identity(active_identity)
    return _write(
        root,
        {
            "version": STATE_VERSION,
            "generation": 0,
            "active": active,
            "candidate": None,
            "last_known_good": active,
            "checksum": "",
        },
    )


def declare_candidate(directory, candidate_identity: object) -> dict:
    current = read_release_state(directory)
    candidate = _identity(candidate_identity)
    if candidate == current["active"] or candidate == current["candidate"]:
        raise ReleaseStateError("candidate must be new")
    return _write(
        directory,
        {
            "version": STATE_VERSION,
            "generation": current["generation"] + 1,
            "active": current["active"],
            "candidate": candidate,
            "last_known_good": current["last_known_good"],
            "checksum": "",
        },
    )


def clear_candidate(directory) -> dict:
    current = read_release_state(directory)
    if current["candidate"] is None:
        raise ReleaseStateError("no candidate to clear")
    return _write(
        directory,
        {
            "version": STATE_VERSION,
            "generation": current["generation"] + 1,
            "active": current["active"],
            "candidate": None,
            "last_known_good": current["last_known_good"],
            "checksum": "",
        },
    )


def commit_candidate(directory) -> dict:
    current = read_release_state(directory)
    candidate = current["candidate"]
    if candidate is None:
        raise ReleaseStateError("no candidate to commit")
    return _write(
        directory,
        {
            "version": STATE_VERSION,
            "generation": current["generation"] + 1,
            "active": candidate,
            "candidate": None,
            "last_known_good": current["active"],
            "checksum": "",
        },
    )


def rollback_to_lkg(directory) -> dict:
    current = read_release_state(directory)
    lkg = current["last_known_good"]
    if lkg == current["active"]:
        raise ReleaseStateError("no distinct last-known-good release")
    return _write(
        directory,
        {
            "version": STATE_VERSION,
            "generation": current["generation"] + 1,
            "active": lkg,
            "candidate": None,
            "last_known_good": lkg,
            "checksum": "",
        },
    )
