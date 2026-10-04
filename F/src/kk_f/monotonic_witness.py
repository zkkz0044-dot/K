"""FH03 strict monotonic witness state machine; privilege transport is separate."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from .input_guard import InputGuardError, read_bounded_text
from .transaction_recovery import TransactionRecoveryError, discard_stale_fixed_temp

VERSION = "0.1"
CHANNELS = frozenset({"restart_ledger", "evidence", "release_state", "safety_state"})
ROOT_KEYS = frozenset({"version", "channels", "checksum"})
CHANNEL_KEYS = frozenset({"generation", "digest", "pending"})
PENDING_KEYS = frozenset({"generation", "digest"})
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class WitnessError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise WitnessError("non-canonical witness value") from exc


def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise WitnessError("duplicate JSON key")
        out[key] = value
    return out


def _digest(value: object) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise WitnessError("lowercase SHA-256 required")
    return value


def _generation(value: object) -> int:
    if type(value) is not int or value < 0:
        raise WitnessError("non-negative integer generation required")
    return value


def _checksum(value: dict) -> str:
    return hashlib.sha256(
        _canonical({"version": value["version"], "channels": value["channels"]})
    ).hexdigest()


def empty_state() -> dict:
    channels = {
        name: {"generation": 0, "digest": "0" * 64, "pending": None} for name in sorted(CHANNELS)
    }
    value = {"version": VERSION, "channels": channels, "checksum": ""}
    value["checksum"] = _checksum(value)
    return value


def validate_state(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != ROOT_KEYS:
        raise WitnessError("exact witness root keys required")
    if value["version"] != VERSION:
        raise WitnessError("unsupported witness version")
    channels = value["channels"]
    if not isinstance(channels, dict) or frozenset(channels) != CHANNELS:
        raise WitnessError("exact witness channels required")
    normalized = {}
    for name in sorted(CHANNELS):
        channel = channels[name]
        if not isinstance(channel, dict) or frozenset(channel) != CHANNEL_KEYS:
            raise WitnessError("exact channel keys required")
        generation = _generation(channel["generation"])
        digest = _digest(channel["digest"])
        pending = channel["pending"]
        if pending is not None:
            if not isinstance(pending, dict) or frozenset(pending) != PENDING_KEYS:
                raise WitnessError("exact pending keys required")
            pg = _generation(pending["generation"])
            pd = _digest(pending["digest"])
            if pg <= generation:
                raise WitnessError("pending generation must advance")
            pending = {"generation": pg, "digest": pd}
        normalized[name] = {"generation": generation, "digest": digest, "pending": pending}
    checksum = value["checksum"]
    result = {"version": VERSION, "channels": normalized, "checksum": checksum}
    if _digest(checksum) != _checksum(result):
        raise WitnessError("witness checksum mismatch")
    return result


def load_state(path: str | os.PathLike[str]) -> dict:
    p = Path(path)
    try:
        raw = read_bounded_text(p, max_bytes=65536)
        value = json.loads(
            raw,
            object_pairs_hook=_strict,
            parse_constant=lambda _: (_ for _ in ()).throw(WitnessError("non-finite number")),
        )
    except WitnessError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, InputGuardError) as exc:
        raise WitnessError("witness state unreadable") from exc
    state = validate_state(value)
    try:
        discard_stale_fixed_temp(p)
    except TransactionRecoveryError as exc:
        raise WitnessError("witness stale-temp recovery failed") from exc
    return state


def save_state(path: str | os.PathLike[str], value: object) -> dict:
    p = Path(path)
    state = validate_state(value)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = p.with_name(p.name + ".tmp")
    data = _canonical(state) + b"\n"
    try:
        discard_stale_fixed_temp(p)
    except TransactionRecoveryError as exc:
        raise WitnessError("witness stale-temp recovery failed") from exc
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        os.replace(temp, p)
        os.chmod(p, 0o600)
        dfd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError as exc:
        raise WitnessError("witness state commit failed") from exc
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
    return state


def _updated(
    state: dict, channel: str, *, generation: int, digest: str, pending: dict | None
) -> dict:
    result = json.loads(_canonical(state))
    result["channels"][channel] = {"generation": generation, "digest": digest, "pending": pending}
    result["checksum"] = _checksum(result)
    return validate_state(result)


def prepare(
    state: object,
    channel: object,
    current_generation: object,
    current_digest: object,
    new_generation: object,
    new_digest: object,
) -> dict:
    state = validate_state(state)
    if channel not in CHANNELS:
        raise WitnessError("unknown witness channel")
    current_generation = _generation(current_generation)
    current_digest = _digest(current_digest)
    new_generation = _generation(new_generation)
    new_digest = _digest(new_digest)
    slot = state["channels"][channel]
    if slot["pending"] is not None:
        raise WitnessError("channel already has pending transition")
    if (slot["generation"], slot["digest"]) != (current_generation, current_digest):
        raise WitnessError("current state does not match witness")
    if new_generation <= current_generation:
        raise WitnessError("new generation must strictly advance")
    return _updated(
        state,
        channel,
        generation=current_generation,
        digest=current_digest,
        pending={"generation": new_generation, "digest": new_digest},
    )


def commit(state: object, channel: object, generation: object, digest: object) -> dict:
    state = validate_state(state)
    if channel not in CHANNELS:
        raise WitnessError("unknown witness channel")
    generation = _generation(generation)
    digest = _digest(digest)
    slot = state["channels"][channel]
    if slot["pending"] != {"generation": generation, "digest": digest}:
        raise WitnessError("commit does not match pending transition")
    return _updated(state, channel, generation=generation, digest=digest, pending=None)


def verify(state: object, channel: object, generation: object, digest: object) -> None:
    state = validate_state(state)
    if channel not in CHANNELS:
        raise WitnessError("unknown witness channel")
    generation = _generation(generation)
    digest = _digest(digest)
    slot = state["channels"][channel]
    if slot["pending"] is not None:
        raise WitnessError("pending transition requires recovery")
    if (slot["generation"], slot["digest"]) != (generation, digest):
        raise WitnessError("state rollback/replay detected")


def recover(
    state: object, channel: object, observed_generation: object, observed_digest: object
) -> dict:
    state = validate_state(state)
    if channel not in CHANNELS:
        raise WitnessError("unknown witness channel")
    observed_generation = _generation(observed_generation)
    observed_digest = _digest(observed_digest)
    slot = state["channels"][channel]
    pending = slot["pending"]
    if pending is None:
        verify(state, channel, observed_generation, observed_digest)
        return state
    if (observed_generation, observed_digest) == (pending["generation"], pending["digest"]):
        return commit(state, channel, observed_generation, observed_digest)
    if (observed_generation, observed_digest) == (slot["generation"], slot["digest"]):
        return _updated(
            state, channel, generation=slot["generation"], digest=slot["digest"], pending=None
        )
    raise WitnessError("observed state matches neither committed nor prepared transition")


def seed_state(bindings: object) -> dict:
    """Root-side provisioning helper; not exposed by the runtime socket protocol."""
    if not isinstance(bindings, dict) or not set(bindings).issubset(CHANNELS):
        raise WitnessError("seed bindings must use known channels")
    state = empty_state()
    for channel, binding in bindings.items():
        if not isinstance(binding, dict) or frozenset(binding) != frozenset(
            {"generation", "digest"}
        ):
            raise WitnessError("exact seed binding required")
        state["channels"][channel] = {
            "generation": _generation(binding["generation"]),
            "digest": _digest(binding["digest"]),
            "pending": None,
        }
    state["checksum"] = _checksum(state)
    return validate_state(state)
