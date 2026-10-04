"""F18/FH05 local Frozen Authority binding the complete worker launch contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat

from .path_guard import PathGuardError, open_absolute_file, read_all_fd
from .process_spec import ProcessSpecError, validate_process_spec

AUTHORITY_VERSION = "0.2"
AUTHORITY_KEYS = frozenset({"version", "authority_id", "process_spec", "max_restart_attempts"})
AUTHORITY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class FrozenAuthorityError(ValueError):
    """Raised when frozen local authority is invalid or denies a candidate."""


def _strict_json(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise FrozenAuthorityError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except FrozenAuthorityError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise FrozenAuthorityError("authority manifest invalid JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != AUTHORITY_KEYS:
        raise FrozenAuthorityError("authority manifest exact keys required")
    return value


def build_frozen_authority(
    authority_id: object, process_spec: object, max_restart_attempts: object
) -> dict:
    if not isinstance(authority_id, str) or not AUTHORITY_ID_RE.fullmatch(authority_id):
        raise FrozenAuthorityError("invalid authority_id")
    try:
        spec = validate_process_spec(process_spec)
    except ProcessSpecError as exc:
        raise FrozenAuthorityError("authority process_spec invalid") from exc
    if type(max_restart_attempts) is not int or max_restart_attempts < 1:
        raise FrozenAuthorityError("positive integer max_restart_attempts required")
    # Deep-copy through canonical JSON primitives so later caller mutation cannot
    # silently change the authority object returned by this constructor.
    frozen_spec = json.loads(
        json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )
    return {
        "version": AUTHORITY_VERSION,
        "authority_id": authority_id,
        "process_spec": frozen_spec,
        "max_restart_attempts": max_restart_attempts,
    }


def _validate_manifest(value: dict) -> dict:
    if value["version"] != AUTHORITY_VERSION:
        raise FrozenAuthorityError("unsupported authority version")
    return build_frozen_authority(
        value["authority_id"], value["process_spec"], value["max_restart_attempts"]
    )


def load_frozen_authority(path: str | os.PathLike[str]) -> dict:
    if not isinstance(path, (str, os.PathLike)):
        raise FrozenAuthorityError("authority path must be absolute")
    value = os.fspath(path)
    fd = -1
    try:
        fd = open_absolute_file(value)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise FrozenAuthorityError("authority manifest must be a real regular file")
        if info.st_uid != 0:
            raise FrozenAuthorityError("authority manifest must be root-owned")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise FrozenAuthorityError("authority manifest must not be group/world writable")
        raw_bytes = read_all_fd(fd, max_bytes=65536)
        try:
            raw = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FrozenAuthorityError("authority manifest unreadable") from exc
    except FrozenAuthorityError:
        raise
    except (PathGuardError, OSError) as exc:
        raise FrozenAuthorityError("authority manifest inaccessible") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    return _validate_manifest(_strict_json(raw))


def authorize_process(path: str | os.PathLike[str], process_spec: object) -> dict:
    manifest = load_frozen_authority(path)
    try:
        spec = validate_process_spec(process_spec)
    except ProcessSpecError as exc:
        raise FrozenAuthorityError("invalid process spec") from exc
    if spec != manifest["process_spec"]:
        raise FrozenAuthorityError("complete process spec not authorized")
    return {
        "authority_id": manifest["authority_id"],
        "executable": spec["executable"],
        "sha256": spec["sha256"],
        "max_restart_attempts": manifest["max_restart_attempts"],
    }
