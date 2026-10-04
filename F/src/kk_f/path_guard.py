"""FH02 canonical absolute path resolution with no symlink traversal in any component."""

from __future__ import annotations

import os
from pathlib import PurePosixPath


class PathGuardError(ValueError):
    """Raised when a critical path is ambiguous or traverses a symlink/non-directory component."""


def _parts(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise PathGuardError("canonical absolute path required")
    if value != "/" and (value.endswith("/") or "//" in value):
        raise PathGuardError("ambiguous absolute path")
    path = PurePosixPath(value)
    parts = path.parts
    if not parts or parts[0] != "/" or any(part in ("", ".", "..") for part in parts[1:]):
        raise PathGuardError("canonical absolute path required")
    if path.as_posix() != value:
        raise PathGuardError("path must be normalized")
    return tuple(parts[1:])


def open_absolute_dir(value: object) -> int:
    parts = _parts(value)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        raise PathGuardError("directory path cannot be resolved without symlinks") from exc


def open_absolute_file(value: object, *, flags: int = os.O_RDONLY | os.O_NONBLOCK) -> int:
    parts = _parts(value)
    if not parts:
        raise PathGuardError("file path cannot be filesystem root")
    parent = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
    parent_fd = open_absolute_dir(parent)
    try:
        try:
            return os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as exc:
            raise PathGuardError("file path cannot be opened without symlinks") from exc
    finally:
        os.close(parent_fd)


def read_all_fd(fd: int, *, max_bytes: int) -> bytes:
    if type(max_bytes) is not int or max_bytes < 1:
        raise PathGuardError("positive max_bytes required")
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(65536, max_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PathGuardError("critical file exceeds size limit")
        chunks.append(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return b"".join(chunks)
