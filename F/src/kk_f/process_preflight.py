"""F10 local process-candidate integrity preflight; no execution."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat

from .process_spec import ProcessSpecError, validate_process_spec


class ProcessPreflightError(ValueError):
    """Raised when the declared process candidate is not safe to execute."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ProcessPreflightError("executable cannot be read") from exc
    return digest.hexdigest()


def verify_process_candidate(spec: object) -> dict:
    try:
        spec = validate_process_spec(spec)
    except ProcessSpecError as exc:
        raise ProcessPreflightError("invalid process spec") from exc
    executable = Path(spec["executable"])
    cwd = Path(spec["cwd"])
    try:
        exe_stat = executable.lstat()
        cwd_stat = cwd.lstat()
    except OSError as exc:
        raise ProcessPreflightError("declared path missing or inaccessible") from exc

    if stat.S_ISLNK(exe_stat.st_mode) or not stat.S_ISREG(exe_stat.st_mode):
        raise ProcessPreflightError("executable must be a regular non-symlink file")
    if not exe_stat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        raise ProcessPreflightError("executable has no execute bit")
    if exe_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ProcessPreflightError("executable cannot be group/world writable")

    if stat.S_ISLNK(cwd_stat.st_mode) or not stat.S_ISDIR(cwd_stat.st_mode):
        raise ProcessPreflightError("cwd must be a real non-symlink directory")

    actual = _sha256(executable)
    if actual != spec["sha256"]:
        raise ProcessPreflightError("executable SHA-256 mismatch")
    return {
        "verified": True,
        "executable": spec["executable"],
        "cwd": spec["cwd"],
        "sha256": actual,
        "size": exe_stat.st_size,
    }
