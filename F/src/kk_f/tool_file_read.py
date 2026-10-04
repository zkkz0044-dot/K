"""F-owned bounded UTF-8 reader restricted to K's own canonical tree."""

from __future__ import annotations

import os
import stat
from .path_guard import PathGuardError, open_absolute_file, read_all_fd

SCHEMA = "F.TOOL.FILE_READ.1"
ROOT = "/root/K/K/"
MAX_BYTES = 65536
MAX_CHARS = 2048
FORBIDDEN = (
    "secret",
    "token",
    "credential",
    "id_rsa",
    "private_key",
    "/.env",
    "/runtime/",
    "/state/",
    "/models/",
    "/vendor/",
)


class FileReadError(RuntimeError):
    pass


def read_project_file(path: object) -> dict:
    if not isinstance(path, str) or not (1 <= len(path) <= 512) or not path.startswith(ROOT):
        raise FileReadError("path denied")
    low = path.lower()
    if any(marker in low for marker in FORBIDDEN):
        raise FileReadError("path denied")
    real = os.path.realpath(path)
    if not real.startswith(ROOT):
        raise FileReadError("path denied")
    fd = -1
    try:
        fd = open_absolute_file(real)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise FileReadError("file policy denied")
        if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise FileReadError("file policy denied")
        data = read_all_fd(fd, max_bytes=MAX_BYTES)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileReadError("utf8 required") from exc
        return {
            "schema": SCHEMA,
            "path": real,
            "content": text[:MAX_CHARS],
            "truncated": len(text) > MAX_CHARS,
        }
    except (PathGuardError, OSError) as exc:
        raise FileReadError("read failed") from exc
    finally:
        if fd >= 0:
            os.close(fd)
