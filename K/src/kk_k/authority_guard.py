"""Root-owned immutable authority-file reader for K constitutional/policy inputs."""

from __future__ import annotations

import os
from pathlib import PurePosixPath
import stat
from pathlib import Path

from .isolation import PROJECT_ROOT

RUNTIME_MIRROR_ROOT = "/run/kk-k-ro"
MAX_MOUNTINFO_BYTES = 1024 * 1024


class AuthorityGuardError(PermissionError):
    pass


def _runtime_mirror_is_readonly_mount() -> bool:
    try:
        raw = Path("/proc/self/mountinfo").read_bytes()
    except OSError:
        return False
    if len(raw) > MAX_MOUNTINFO_BYTES:
        return False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[3] == str(PROJECT_ROOT) and parts[4] == RUNTIME_MIRROR_ROOT:
            return "ro" in parts[5].split(",")
    return False


def _normalize_under_root(path: object) -> str:
    if not isinstance(path, (str, os.PathLike)):
        raise AuthorityGuardError("authority path must be pathlike")
    raw = os.fspath(path)
    if "\x00" in raw:
        raise AuthorityGuardError("NUL forbidden")
    candidate = raw if raw.startswith("/") else os.path.join(str(PROJECT_ROOT), raw)
    normalized = os.path.normpath(candidate)
    project = str(PROJECT_ROOT)
    mirror_ok = _runtime_mirror_is_readonly_mount()
    try:
        if os.path.commonpath([normalized, project]) == project:
            if mirror_ok:
                rel = os.path.relpath(normalized, project)
                return os.path.normpath(os.path.join(RUNTIME_MIRROR_ROOT, rel))
            return normalized
    except ValueError:
        pass
    if mirror_ok:
        try:
            if os.path.commonpath([normalized, RUNTIME_MIRROR_ROOT]) == RUNTIME_MIRROR_ROOT:
                return normalized
        except ValueError:
            pass
    raise AuthorityGuardError("authority path escapes verified K roots")


def _open_no_symlinks(path: str) -> int:
    pp = PurePosixPath(path)
    parts = pp.parts
    if not parts or parts[0] != "/":
        raise AuthorityGuardError("absolute authority path required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[1:-1]:
            if part in ("", ".", ".."):
                raise AuthorityGuardError("ambiguous authority path")
            nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nfd
        leaf = parts[-1]
        if leaf in ("", ".", ".."):
            raise AuthorityGuardError("invalid authority filename")
        try:
            out = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except OSError as exc:
            raise AuthorityGuardError("authority file cannot be opened without symlinks") from exc
        return out
    except AuthorityGuardError:
        raise
    except OSError as exc:
        raise AuthorityGuardError("authority path cannot be traversed without symlinks") from exc
    finally:
        os.close(fd)


def read_root_authority(path: object, *, max_bytes: int) -> str:
    if type(max_bytes) is not int or max_bytes < 1:
        raise AuthorityGuardError("positive max_bytes required")
    normalized = _normalize_under_root(path)
    fd = -1
    try:
        fd = _open_no_symlinks(normalized)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise AuthorityGuardError("authority must be regular file")
        if info.st_uid != 0:
            raise AuthorityGuardError("authority must be root-owned")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise AuthorityGuardError("authority must not be group/world writable")
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise AuthorityGuardError("authority exceeds size limit")
            chunks.append(chunk)
        try:
            return b"".join(chunks).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AuthorityGuardError("authority must be UTF-8") from exc
    finally:
        if fd >= 0:
            os.close(fd)
