from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path

from .path_guard import PathGuardError, open_absolute_dir, open_absolute_file, read_all_fd

SCHEMA = "FK_AUDIT.WITNESS.2"
STATE_KEYS = frozenset({"schema", "generation", "digest", "checksum"})
EVENT_BASE_KEYS = frozenset(
    {"schema", "sequence", "event_id", "kind", "subject", "summary", "prev_sha256"}
)
EVENT_KEYS = EVENT_BASE_KEYS | {"entry_sha256"}
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
KINDS = frozenset({"DECISION", "EXECUTION", "OBSERVATION", "USER_NOTE", "SYSTEM"})
ZERO_DIGEST = "0" * 64
MAX_STATE_BYTES = 4096
MAX_LOG_BYTES = 16 * 1024 * 1024  # legacy single-file compatibility ceiling
SEGMENT_TARGET_BYTES = 1024 * 1024
MAX_SEGMENT_BYTES = 2 * 1024 * 1024
SEGMENT_DIGITS = 6
MAX_EVENT_TAIL_BYTES = 8192


class KAuditWitnessError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KAuditWitnessError("NON_CANONICAL_VALUE") from exc


def _checksum(generation: int, digest: str) -> str:
    return hashlib.sha256(
        _canonical({"schema": SCHEMA, "generation": generation, "digest": digest})
    ).hexdigest()


def build_state(generation: object, digest: object) -> dict:
    if type(generation) is not int or generation < 0:
        raise KAuditWitnessError("INVALID_GENERATION")
    if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
        raise KAuditWitnessError("INVALID_DIGEST")
    if generation == 0 and digest != ZERO_DIGEST:
        raise KAuditWitnessError("ZERO_STATE_MISMATCH")
    return {
        "schema": SCHEMA,
        "generation": generation,
        "digest": digest,
        "checksum": _checksum(generation, digest),
    }


def validate_state(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != STATE_KEYS:
        raise KAuditWitnessError("WITNESS_INVALID")
    if value.get("schema") != SCHEMA:
        raise KAuditWitnessError("WITNESS_INVALID")
    try:
        expected = build_state(value["generation"], value["digest"])
    except KAuditWitnessError as exc:
        raise KAuditWitnessError("WITNESS_INVALID") from exc
    if value["checksum"] != expected["checksum"]:
        raise KAuditWitnessError("WITNESS_INVALID")
    return expected


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise KAuditWitnessError("WITNESS_INVALID")
        out[key] = value
    return out


def _canonical_event_base(value: dict) -> bytes:
    return _canonical({key: value[key] for key in EVENT_BASE_KEYS})


def validate_event(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != EVENT_KEYS:
        raise KAuditWitnessError("EVENT_INVALID")
    if value["schema"] != "K02.EVENT.1":
        raise KAuditWitnessError("EVENT_INVALID")
    if type(value["sequence"]) is not int or value["sequence"] < 1:
        raise KAuditWitnessError("EVENT_INVALID")
    if not isinstance(value["event_id"], str) or EVENT_ID_RE.fullmatch(value["event_id"]) is None:
        raise KAuditWitnessError("EVENT_INVALID")
    if value["kind"] not in KINDS:
        raise KAuditWitnessError("EVENT_INVALID")
    for field, limit in (("subject", 256), ("summary", 2048)):
        if not isinstance(value[field], str) or not (
            1 <= len(value[field].encode("utf-8")) <= limit
        ):
            raise KAuditWitnessError("EVENT_INVALID")
    for field in ("prev_sha256", "entry_sha256"):
        if not isinstance(value[field], str) or HEX64.fullmatch(value[field]) is None:
            raise KAuditWitnessError("EVENT_INVALID")
    expected = hashlib.sha256(_canonical_event_base(value)).hexdigest()
    if value["entry_sha256"] != expected:
        raise KAuditWitnessError("EVENT_DIGEST_MISMATCH")
    return dict(value)


def load_state(path: str) -> dict:
    fd = -1
    try:
        fd = open_absolute_file(path)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise KAuditWitnessError("WITNESS_INVALID")
        raw = read_all_fd(fd, max_bytes=MAX_STATE_BYTES)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("WITNESS_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs)
    except KAuditWitnessError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise KAuditWitnessError("WITNESS_INVALID") from exc
    return validate_state(value)


def _split_path(path: str) -> tuple[str, str]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise KAuditWitnessError("WITNESS_INVALID")
    p = Path(path)
    if p.as_posix() != path or p.name in {"", ".", ".."}:
        raise KAuditWitnessError("WITNESS_INVALID")
    return p.parent.as_posix(), p.name


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    total = 0
    while total < len(data):
        written = os.write(fd, view[total:])
        if written <= 0:
            raise KAuditWitnessError("WITNESS_WRITE_FAILED")
        total += written


def _atomic_replace(path: str, state: dict) -> None:
    parent, name = _split_path(path)
    parent_fd = temp_fd = -1
    temp_name = f".{name}.tmp.{os.getpid()}.{secrets.token_hex(6)}"
    data = _canonical(validate_state(state)) + b"\n"
    try:
        parent_fd = open_absolute_dir(parent)
        temp_fd = os.open(
            temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd
        )
        _write_all(temp_fd, data)
        os.fchmod(temp_fd, 0o600)
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = -1
        os.replace(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("WITNESS_WRITE_FAILED") from exc
    finally:
        if temp_fd >= 0:
            os.close(temp_fd)
        if parent_fd >= 0:
            try:
                os.unlink(temp_name, dir_fd=parent_fd)
            except OSError:
                pass
            os.close(parent_fd)


def initialize_state(path: str) -> dict:
    parent, name = _split_path(path)
    parent_fd = fd = -1
    state = build_state(0, ZERO_DIGEST)
    try:
        parent_fd = open_absolute_dir(parent)
        try:
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd
            )
        except FileExistsError:
            return load_state(path)
        _write_all(fd, _canonical(state) + b"\n")
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        os.fsync(parent_fd)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("WITNESS_WRITE_FAILED") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if parent_fd >= 0:
            os.close(parent_fd)
    return state


def _initialize_log(path: str) -> None:
    parent, name = _split_path(path)
    parent_fd = fd = -1
    try:
        parent_fd = open_absolute_dir(parent)
        try:
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd
            )
        except FileExistsError:
            return
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        os.fsync(parent_fd)
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _segment_path(path: str, index: int) -> str:
    if type(index) is not int or index < 1:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID")
    return path if index == 1 else f"{path}.seg.{index:0{SEGMENT_DIGITS}d}"


def _segment_paths(path: str) -> list[str]:
    _initialize_log(path)
    parent, name = _split_path(path)
    parent_fd = -1
    try:
        parent_fd = open_absolute_dir(parent)
        names = os.listdir(parent_fd)
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if parent_fd >= 0:
            os.close(parent_fd)
    prefix = name + ".seg."
    indices = [1]
    for candidate in names:
        if not candidate.startswith(prefix):
            continue
        suffix = candidate[len(prefix) :]
        if len(suffix) != SEGMENT_DIGITS or not suffix.isdigit():
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        index = int(suffix)
        if index < 2:
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        indices.append(index)
    indices = sorted(set(indices))
    if indices != list(range(1, indices[-1] + 1)):
        raise KAuditWitnessError("CANONICAL_LOG_INVALID")
    return [_segment_path(path, index) for index in indices]


def _read_segment(path: str) -> bytes:
    fd = -1
    try:
        fd = open_absolute_file(path)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        return read_all_fd(fd, max_bytes=MAX_SEGMENT_BYTES)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def iter_canonical_events(path: str):
    segment_paths = _segment_paths(path)
    expected_sequence = 1
    prev = ZERO_DIGEST
    for segment_index, segment_path in enumerate(segment_paths, start=1):
        raw = _read_segment(segment_path)
        if raw and not raw.endswith(b"\n"):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        if not raw and segment_index != len(segment_paths):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
        for line in text.splitlines():
            try:
                value = json.loads(line, object_pairs_hook=_strict_pairs)
            except KAuditWitnessError:
                raise
            except (json.JSONDecodeError, TypeError) as exc:
                raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
            checked = validate_event(value)
            if checked["sequence"] != expected_sequence or checked["prev_sha256"] != prev:
                raise KAuditWitnessError("CANONICAL_LOG_INVALID")
            yield checked
            expected_sequence += 1
            prev = checked["entry_sha256"]


def load_canonical_events(path: str) -> list[dict]:
    return list(iter_canonical_events(path))


def canonical_head(path: str) -> tuple[int, str]:
    generation = 0
    digest = ZERO_DIGEST
    for event in iter_canonical_events(path):
        generation = event["sequence"]
        digest = event["entry_sha256"]
    return generation, digest


def _last_event_from_segment(path: str) -> dict | None:
    fd = -1
    try:
        fd = open_absolute_file(path)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        size = info.st_size
        if size == 0:
            return None
        if size > MAX_SEGMENT_BYTES:
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        start = max(0, size - MAX_EVENT_TAIL_BYTES)
        os.lseek(fd, start, os.SEEK_SET)
        raw = bytearray()
        while len(raw) < size - start:
            chunk = os.read(fd, (size - start) - len(raw))
            if not chunk:
                break
            raw.extend(chunk)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    data = bytes(raw)
    if len(data) != size - start or not data.endswith(b"\n"):
        raise KAuditWitnessError("CANONICAL_LOG_INVALID")
    lines = data.splitlines()
    if start > 0:
        if b"\n" not in data:
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        lines = lines[1:]
    if not lines:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID")
    try:
        value = json.loads(lines[-1].decode("utf-8"), object_pairs_hook=_strict_pairs)
    except KAuditWitnessError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    return validate_event(value)


def canonical_tail(path: str) -> tuple[int, str, str]:
    segment_paths = _segment_paths(path)
    last = _last_event_from_segment(segment_paths[-1])
    if last is None:
        if len(segment_paths) == 1:
            return 0, ZERO_DIGEST, ZERO_DIGEST
        last = _last_event_from_segment(segment_paths[-2])
        if last is None:
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
    return last["sequence"], last["entry_sha256"], last["prev_sha256"]


def _recover_canonical_tail(state_path: str, log_path: str) -> dict:
    state = load_state(state_path)
    generation, digest, prev = canonical_tail(log_path)
    if generation == state["generation"]:
        if digest != state["digest"]:
            raise KAuditWitnessError("CANONICAL_LOG_MISMATCH")
        return state
    if generation == state["generation"] + 1 and prev == state["digest"]:
        new_state = build_state(generation, digest)
        _atomic_replace(state_path, new_state)
        return load_state(state_path)
    raise KAuditWitnessError("CANONICAL_LOG_MISMATCH")


def _create_segment(path: str) -> None:
    parent, name = _split_path(path)
    parent_fd = fd = -1
    try:
        parent_fd = open_absolute_dir(parent)
        fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd
        )
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        os.fsync(parent_fd)
    except FileExistsError:
        return
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _seal_segment(path: str) -> None:
    fd = -1
    try:
        fd = open_absolute_file(path)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        os.fchmod(fd, 0o400)
        os.fsync(fd)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def recover_canonical_tail(state_path: str, log_path: str) -> dict:
    return _recover_canonical_tail(state_path, log_path)


def _append_canonical_event(path: str, event: dict) -> None:
    segment_paths = _segment_paths(path)
    data = _canonical(validate_event(event)) + b"\n"
    active = segment_paths[-1]
    fd = -1
    try:
        fd = open_absolute_file(active)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        current_size = info.st_size
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    if current_size + len(data) > SEGMENT_TARGET_BYTES and current_size > 0:
        generation, digest = canonical_head(path)
        if generation != event["sequence"] - 1 or digest != event["prev_sha256"]:
            raise KAuditWitnessError("CANONICAL_LOG_MISMATCH")
        _seal_segment(active)
        active = _segment_path(path, len(segment_paths) + 1)
        _create_segment(active)
        current_size = 0
    if current_size + len(data) > MAX_SEGMENT_BYTES:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID")
    fd = -1
    try:
        fd = open_absolute_file(active, flags=os.O_WRONLY | os.O_APPEND)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise KAuditWitnessError("CANONICAL_LOG_INVALID")
        _write_all(fd, data)
        os.fsync(fd)
    except KAuditWitnessError:
        raise
    except (PathGuardError, OSError) as exc:
        raise KAuditWitnessError("CANONICAL_LOG_INVALID") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def recover_canonical(state_path: str, log_path: str) -> dict:
    state = load_state(state_path)
    generation = 0
    digest = ZERO_DIGEST
    last_prev = ZERO_DIGEST
    for event in iter_canonical_events(log_path):
        generation = event["sequence"]
        last_prev = event["prev_sha256"]
        digest = event["entry_sha256"]
    if generation == state["generation"]:
        if digest != state["digest"]:
            raise KAuditWitnessError("CANONICAL_LOG_MISMATCH")
        return state
    if generation == state["generation"] + 1:
        if last_prev != state["digest"]:
            raise KAuditWitnessError("CANONICAL_LOG_MISMATCH")
        new_state = build_state(generation, digest)
        _atomic_replace(state_path, new_state)
        return load_state(state_path)
    raise KAuditWitnessError("CANONICAL_LOG_MISMATCH")


def commit_event(path: str, event: object, *, canonical_log_path: str | None = None) -> dict:
    current = (
        _recover_canonical_tail(path, canonical_log_path)
        if canonical_log_path is not None
        else load_state(path)
    )
    checked = validate_event(event)
    if checked["sequence"] != current["generation"] + 1:
        raise KAuditWitnessError("GENERATION_MISMATCH")
    if checked["prev_sha256"] != current["digest"]:
        raise KAuditWitnessError("PREV_DIGEST_MISMATCH")
    if canonical_log_path is not None:
        _append_canonical_event(canonical_log_path, checked)
    new_state = build_state(checked["sequence"], checked["entry_sha256"])
    _atomic_replace(path, new_state)
    return load_state(path)
