from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .isolation import project_path

GOAL_KEYS = frozenset({"schema", "goal_id", "text", "status"})
EVENT_BASE_KEYS = frozenset(
    {"schema", "sequence", "event_id", "kind", "subject", "summary", "prev_sha256"}
)
EVENT_KEYS = EVENT_BASE_KEYS | {"entry_sha256"}
GOAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
KINDS = frozenset({"DECISION", "EXECUTION", "OBSERVATION", "USER_NOTE", "SYSTEM"})
MAX_EVENT_LOG_BYTES = 4 * 1024 * 1024
ZERO_HASH = "0" * 64


class MemoryError(ValueError):
    pass


def _strict_json(raw: str, keys: frozenset[str], label: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise MemoryError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except MemoryError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise MemoryError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise MemoryError(f"exact {label} fields required")
    return value


def validate_goal(value: dict) -> dict:
    if value["schema"] != "K02.GOAL.1":
        raise MemoryError("unsupported goal schema")
    if not isinstance(value["goal_id"], str) or not GOAL_ID_RE.fullmatch(value["goal_id"]):
        raise MemoryError("invalid goal_id")
    if not isinstance(value["text"], str) or not (1 <= len(value["text"].encode("utf-8")) <= 4096):
        raise MemoryError("invalid goal text")
    if value["status"] not in {"ACTIVE", "PAUSED", "DONE"}:
        raise MemoryError("invalid goal status")
    return dict(value)


def load_goal(path: str) -> dict:
    raw = project_path(path, must_exist=True).read_text(encoding="utf-8")
    if len(raw.encode("utf-8")) > 8192:
        raise MemoryError("goal file too large")
    return validate_goal(_strict_json(raw, GOAL_KEYS, "goal"))


def write_goal_atomic(path: str, value: dict) -> None:
    checked = validate_goal(_strict_json(json.dumps(value, ensure_ascii=False), GOAL_KEYS, "goal"))
    data = (
        json.dumps(checked, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    p = project_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, p)
        dfd = os.open(str(p.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)


def _canonical_base(value: dict) -> bytes:
    base = {k: value[k] for k in EVENT_BASE_KEYS}
    return json.dumps(
        base, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _validate_event(value: dict, expected_sequence: int, expected_prev: str) -> dict:
    if value["schema"] != "K02.EVENT.1":
        raise MemoryError("unsupported event schema")
    if type(value["sequence"]) is not int or value["sequence"] != expected_sequence:
        raise MemoryError("invalid event sequence")
    if not isinstance(value["event_id"], str) or not EVENT_ID_RE.fullmatch(value["event_id"]):
        raise MemoryError("invalid event_id")
    if value["kind"] not in KINDS:
        raise MemoryError("invalid event kind")
    for field, limit in (("subject", 256), ("summary", 2048)):
        if not isinstance(value[field], str) or not (
            1 <= len(value[field].encode("utf-8")) <= limit
        ):
            raise MemoryError(f"invalid event {field}")
    if value["prev_sha256"] != expected_prev:
        raise MemoryError("event chain mismatch")
    expected_hash = hashlib.sha256(_canonical_base(value)).hexdigest()
    if value["entry_sha256"] != expected_hash:
        raise MemoryError("event digest mismatch")
    return dict(value)


def verify_event_log(path: str) -> list[dict]:
    p = project_path(path)
    if not p.exists():
        return []
    raw = p.read_bytes()
    if len(raw) > MAX_EVENT_LOG_BYTES:
        raise MemoryError("event log too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MemoryError("event log must be UTF-8") from exc
    if text and not text.endswith("\n"):
        raise MemoryError("unterminated event record")
    out = []
    prev = ZERO_HASH
    for index, line in enumerate(text.splitlines(), start=1):
        value = _strict_json(line, EVENT_KEYS, "event")
        checked = _validate_event(value, index, prev)
        out.append(checked)
        prev = checked["entry_sha256"]
    return out


def append_event(path: str, *, event_id: str, kind: str, subject: str, summary: str) -> dict:
    records = verify_event_log(path)
    sequence = len(records) + 1
    prev = records[-1]["entry_sha256"] if records else ZERO_HASH
    base = {
        "schema": "K02.EVENT.1",
        "sequence": sequence,
        "event_id": event_id,
        "kind": kind,
        "subject": subject,
        "summary": summary,
        "prev_sha256": prev,
    }
    value = dict(base)
    value["entry_sha256"] = hashlib.sha256(_canonical_base(value)).hexdigest()
    checked = _validate_event(value, sequence, prev)
    data = (
        json.dumps(checked, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    p = project_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    if not existed:
        dfd = os.open(str(p.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    return checked
