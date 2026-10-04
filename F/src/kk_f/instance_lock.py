"""FP02 explicit single-instance lock using local kernel file locking."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import stat


class InstanceLockError(RuntimeError):
    """Raised when a runtime instance lock cannot be safely acquired or released."""


class InstanceLock:
    def __init__(self, path: Path, fd: int):
        self.path = path
        self._fd = fd
        self._released = False

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        if self._released:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError as exc:
            raise InstanceLockError("instance lock release failed") from exc
        finally:
            try:
                os.close(self._fd)
            finally:
                self._released = True

    def __enter__(self) -> "InstanceLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def _validate_existing_lock_file(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise InstanceLockError("instance lock path inaccessible") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise InstanceLockError("instance lock must be a real regular file")
    if info.st_uid != os.geteuid():
        raise InstanceLockError("instance lock owner mismatch")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise InstanceLockError("instance lock must not be group/world writable")


def acquire_instance_lock(path: str | os.PathLike[str]) -> InstanceLock:
    lock_path = Path(path)
    if not lock_path.is_absolute():
        raise InstanceLockError("instance lock path must be absolute")
    _validate_existing_lock_file(lock_path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
    except OSError as exc:
        raise InstanceLockError("instance lock open failed") from exc
    try:
        current = os.fstat(fd)
        if not stat.S_ISREG(current.st_mode) or current.st_uid != os.geteuid():
            raise InstanceLockError("instance lock changed identity during open")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InstanceLockError("another F runtime instance already holds the lock") from exc
        payload = (
            json.dumps({"pid": os.getpid()}, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        os.ftruncate(fd, 0)
        os.write(fd, payload)
        os.fsync(fd)
        return InstanceLock(lock_path, fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
