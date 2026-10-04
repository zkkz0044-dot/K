from __future__ import annotations

import json
import os

from .isolation import project_path

MAX_AUDIT_BYTES = 4096


class AuditError(OSError):
    pass


def append_jsonl(path: str | os.PathLike[str], record: object) -> None:
    try:
        raw = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise AuditError("audit record is not canonical JSON") from exc
    data = (raw + "\n").encode("utf-8")
    if len(data) > MAX_AUDIT_BYTES:
        raise AuditError("audit record too large")

    p = project_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
