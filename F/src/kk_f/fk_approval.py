from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import time

from .path_guard import PathGuardError, open_absolute_file, read_all_fd

SCHEMA = "FKP01.APPROVAL.1"
ACTION_ID = "A03_RUN_F_SMOKE_TEST"
APPROVAL_PATH = "/root/K/FK/state/a03_approval.json"
ROOT = Path("/root/K/FK").resolve()
KEYS = frozenset({"schema", "action_id", "nonce", "issued_at", "expires_at"})
HEX32 = re.compile(r"^[0-9a-f]{32}$")
MAX_TTL = 300
MAX_BYTES = 4096


class FKApprovalError(ValueError):
    pass


def _strict(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise FKApprovalError("duplicate approval key")
            out[k] = v
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except FKApprovalError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise FKApprovalError("invalid approval JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != KEYS:
        raise FKApprovalError("exact approval fields required")
    return value


def _validate(value: dict) -> dict:
    if value["schema"] != SCHEMA or value["action_id"] != ACTION_ID:
        raise FKApprovalError("approval identity mismatch")
    if not isinstance(value["nonce"], str) or HEX32.fullmatch(value["nonce"]) is None:
        raise FKApprovalError("invalid approval nonce")
    for key in ("issued_at", "expires_at"):
        if type(value[key]) is not int or value[key] < 0:
            raise FKApprovalError("invalid approval time")
    ttl = value["expires_at"] - value["issued_at"]
    if ttl < 1 or ttl > MAX_TTL:
        raise FKApprovalError("invalid approval ttl")
    return dict(value)


def _path(value: str) -> Path:
    if not isinstance(value, str) or not value.startswith("/"):
        raise FKApprovalError("absolute approval path required")
    p = Path(value)
    normalized = Path(os.path.normpath(value))
    try:
        common = Path(os.path.commonpath([str(normalized), str(ROOT)]))
    except ValueError as exc:
        raise FKApprovalError("approval path invalid") from exc
    if common != ROOT or normalized.name != "a03_approval.json":
        raise FKApprovalError("approval path outside FK state")
    return normalized


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    os.chown(p.parent, 0, 0)
    os.chmod(p.parent, 0o700)


def issue_a03_approval(
    *,
    ttl_seconds: int,
    now_epoch: int | None = None,
    path: str = APPROVAL_PATH,
    nonce: str | None = None,
) -> dict:
    if os.geteuid() != 0:
        raise FKApprovalError("root/F authority required")
    if type(ttl_seconds) is not int or not (1 <= ttl_seconds <= MAX_TTL):
        raise FKApprovalError("approval ttl out of range")
    p = _path(path)
    _ensure_parent(p)
    if p.exists() or p.is_symlink():
        raise FKApprovalError("unconsumed approval already exists")
    now = int(time.time()) if now_epoch is None else now_epoch
    if type(now) is not int or now < 0:
        raise FKApprovalError("invalid issue time")
    token = secrets.token_hex(16) if nonce is None else nonce
    value = _validate(
        {
            "schema": SCHEMA,
            "action_id": ACTION_ID,
            "nonce": token,
            "issued_at": now,
            "expires_at": now + ttl_seconds,
        }
    )
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".a03-approval-", suffix=".tmp", dir=str(p.parent))
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, 0, 0)
        if os.write(fd, raw) != len(raw):
            raise FKApprovalError("short approval write")
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, p)
        dfd = os.open(str(p.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
    return value


def _archive(p: Path, nonce: str, prefix: str) -> None:
    consumed = p.parent / "consumed"
    consumed.mkdir(mode=0o700, exist_ok=True)
    os.chown(consumed, 0, 0)
    os.chmod(consumed, 0o700)
    target = consumed / f"{prefix}-{nonce}.json"
    if target.exists():
        raise FKApprovalError("approval replay archive collision")
    os.replace(p, target)
    dfd = os.open(str(p.parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def consume_a03_approval(
    *, now_epoch: int | None = None, path: str = APPROVAL_PATH
) -> tuple[bool, str, dict | None]:
    p = _path(path)
    if not p.exists():
        return False, "HUMAN_APPROVAL_REQUIRED", None
    fd = -1
    try:
        fd = open_absolute_file(str(p))
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or (info.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
        ):
            raise FKApprovalError("approval authority metadata invalid")
        raw = read_all_fd(fd, max_bytes=MAX_BYTES)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FKApprovalError("approval must be UTF-8") from exc
        value = _validate(_strict(text))
        now = int(time.time()) if now_epoch is None else now_epoch
        if type(now) is not int or now < 0:
            raise FKApprovalError("invalid consume time")
        if now < value["issued_at"]:
            raise FKApprovalError("approval issued in future")
        if now > value["expires_at"]:
            _archive(p, value["nonce"], "expired")
            return False, "HUMAN_APPROVAL_EXPIRED", value
        _archive(p, value["nonce"], "used")
        return True, "HUMAN_APPROVAL_ACCEPTED", value
    except (PathGuardError, OSError) as exc:
        raise FKApprovalError("approval inaccessible") from exc
    finally:
        if fd >= 0:
            os.close(fd)
