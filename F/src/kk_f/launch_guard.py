"""FH01 bind integrity verification to the exact executable/cwd objects used at launch."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass

from .path_guard import PathGuardError, open_absolute_dir, open_absolute_file
from .process_spec import ProcessSpecError, validate_process_spec


class LaunchGuardError(ValueError):
    """Raised when launch objects are ambiguous, mutable, or changed during verification."""


@dataclass
class VerifiedLaunch:
    spec: dict
    executable_fd: int
    cwd_fd: int
    sha256: str
    size: int
    device: int
    inode: int

    @property
    def executable_ref(self) -> str:
        return f"/proc/self/fd/{self.executable_fd}"

    @property
    def cwd_ref(self) -> str:
        return f"/proc/self/fd/{self.cwd_fd}"

    @property
    def pass_fds(self) -> tuple[int, int]:
        return (self.executable_fd, self.cwd_fd)

    def close(self) -> None:
        for fd in (self.executable_fd, self.cwd_fd):
            try:
                os.close(fd)
            except OSError:
                pass
        self.executable_fd = -1
        self.cwd_fd = -1


def _stable_identity(st: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        st.st_dev,
        st.st_ino,
        st.st_mode,
        st.st_nlink,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )


def _hash_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def open_verified_launch(spec: object) -> VerifiedLaunch:
    try:
        normalized = validate_process_spec(spec)
    except ProcessSpecError as exc:
        raise LaunchGuardError("invalid process spec") from exc

    efd = -1
    cfd = -1
    try:
        efd = open_absolute_file(normalized["executable"])
        before = os.fstat(efd)
        if not stat.S_ISREG(before.st_mode):
            raise LaunchGuardError("executable must be a regular file")
        if before.st_nlink != 1:
            raise LaunchGuardError("executable must have exactly one hard link")
        if not before.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise LaunchGuardError("executable has no execute bit")
        if before.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise LaunchGuardError("executable cannot be group/world writable")
        digest = _hash_fd(efd)
        after = os.fstat(efd)
        if _stable_identity(before) != _stable_identity(after):
            raise LaunchGuardError("executable changed during verification")
        if digest != normalized["sha256"]:
            raise LaunchGuardError("executable SHA-256 mismatch")

        cfd = open_absolute_dir(normalized["cwd"])
        cwd_st = os.fstat(cfd)
        if not stat.S_ISDIR(cwd_st.st_mode):
            raise LaunchGuardError("cwd must be a real directory")

        return VerifiedLaunch(
            spec=normalized,
            executable_fd=efd,
            cwd_fd=cfd,
            sha256=digest,
            size=before.st_size,
            device=before.st_dev,
            inode=before.st_ino,
        )
    except LaunchGuardError:
        if efd >= 0:
            os.close(efd)
        if cfd >= 0:
            os.close(cfd)
        raise
    except (OSError, PathGuardError) as exc:
        if efd >= 0:
            os.close(efd)
        if cfd >= 0:
            os.close(cfd)
        raise LaunchGuardError("launch object cannot be opened safely") from exc
