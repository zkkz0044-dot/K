from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path("/root/K/K").resolve()


class IsolationError(PermissionError):
    pass


def project_path(path, *, must_exist=False):
    if not isinstance(path, (str, os.PathLike)):
        raise IsolationError("path must be string/pathlike")
    raw = Path(path)
    candidate = raw if raw.is_absolute() else PROJECT_ROOT / raw
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise IsolationError("path resolution failed") from exc
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise IsolationError("path escapes KK/K project root")
    if must_exist and not resolved.exists():
        raise IsolationError("required project path missing")
    return resolved


def assert_project_path(path, *, must_exist=False):
    return str(project_path(path, must_exist=must_exist))
