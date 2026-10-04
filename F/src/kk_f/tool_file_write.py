"""F-owned atomic text writer restricted to K workspace."""

from __future__ import annotations
import hashlib, os, pathlib, tempfile

SCHEMA = "F.TOOL.FILE_WRITE.1"
ROOT = pathlib.Path("/root/K/K/workspace").resolve()
MAX_BYTES = 16384
ALLOWED_SUFFIXES = frozenset({".txt", ".md", ".json"})


class FileWriteError(RuntimeError):
    pass


def _target(path: object) -> pathlib.Path:
    if not isinstance(path, str) or not (1 <= len(path) <= 512):
        raise FileWriteError("path denied")
    p = pathlib.Path(path)
    if not p.is_absolute() or p.suffix.lower() not in ALLOWED_SUFFIXES:
        raise FileWriteError("path denied")
    try:
        rel = p.relative_to(ROOT)
    except ValueError as exc:
        raise FileWriteError("path denied") from exc
    if len(rel.parts) != 1 or any(x in {".", ".."} or x.startswith(".") for x in rel.parts):
        raise FileWriteError("path denied")
    parent = p.parent.resolve(strict=True)
    if parent != ROOT and ROOT not in parent.parents:
        raise FileWriteError("path denied")
    return p


def write_workspace_file(path: object, content: object) -> dict:
    if not isinstance(content, str):
        raise FileWriteError("content denied")
    raw = content.encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise FileWriteError("content too large")
    p = _target(path)
    if os.path.lexists(p):
        raise FileWriteError("overwrite denied")
    fd, tmp = tempfile.mkstemp(prefix=".kk-write-", dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        if os.path.lexists(p):
            raise FileWriteError("overwrite denied")
        os.link(tmp, p)
        os.unlink(tmp)
        dfd = os.open(str(p.parent), os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except FileWriteError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise FileWriteError("write failed") from exc
    return {
        "schema": SCHEMA,
        "path": str(p),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "created": True,
    }
