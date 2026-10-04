"""FS02 exact on-disk release-tree verification; read-only and fail-closed."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Iterable

from .release_manifest import ReleaseManifestError, validate_release_manifest


class ReleaseTreeError(ValueError):
    """Raised when local release bytes do not exactly match the verified manifest."""


def _validate_root(root: str | os.PathLike[str]) -> Path:
    path = Path(root)
    if not path.is_absolute():
        raise ReleaseTreeError("release root must be absolute")
    try:
        st = path.lstat()
    except OSError as exc:
        raise ReleaseTreeError("release root is unavailable") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise ReleaseTreeError("release root must be a real directory, not a symlink")
    return path


def _open_declared_file(root: Path, relative_path: str) -> tuple[int, os.stat_result]:
    parts = relative_path.split("/")
    root_fd = -1
    current_fd = -1
    try:
        root_fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current_fd = root_fd
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        leaf_st = os.stat(parts[-1], dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(leaf_st.st_mode):
            raise ReleaseTreeError("declared path is not a regular file")
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=current_fd)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            raise ReleaseTreeError("declared path is not a regular file")
        return fd, st
    except ReleaseTreeError:
        raise
    except OSError as exc:
        raise ReleaseTreeError("declared file cannot be opened safely") from exc
    finally:
        if current_fd >= 0 and current_fd != root_fd:
            os.close(current_fd)
        if root_fd >= 0:
            os.close(root_fd)


def _sha256_fd(fd: int) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _iter_tree_entries(root: Path) -> Iterable[str]:
    base = str(root)
    try:
        for current, dirs, files in os.walk(base, topdown=True, followlinks=False):
            current_path = Path(current)
            for name in list(dirs):
                child = current_path / name
                try:
                    st = child.lstat()
                except OSError as exc:
                    raise ReleaseTreeError("release tree entry became unavailable") from exc
                relative = child.relative_to(root).as_posix()
                if stat.S_ISLNK(st.st_mode):
                    yield relative
                    dirs.remove(name)
                elif not stat.S_ISDIR(st.st_mode):
                    yield relative
                    dirs.remove(name)
                else:
                    yield relative + "/"
            for name in files:
                child = current_path / name
                try:
                    child.lstat()
                except OSError as exc:
                    raise ReleaseTreeError("release tree entry became unavailable") from exc
                yield child.relative_to(root).as_posix()
    except ReleaseTreeError:
        raise
    except OSError as exc:
        raise ReleaseTreeError("release tree cannot be scanned safely") from exc


def verify_release_tree(root: str | os.PathLike[str], manifest: object) -> dict:
    try:
        verified_manifest = validate_release_manifest(manifest)
    except ReleaseManifestError as exc:
        raise ReleaseTreeError("release manifest is invalid") from exc
    release_root = _validate_root(root)
    declared = {record["path"]: record for record in verified_manifest["files"]}

    observed_entries = set(_iter_tree_entries(release_root))
    expected_entries = set(declared)
    for relative_path in declared:
        parts = relative_path.split("/")
        for index in range(1, len(parts)):
            expected_entries.add("/".join(parts[:index]) + "/")
    undeclared = observed_entries - expected_entries
    if undeclared:
        raise ReleaseTreeError("release tree contains undeclared entries")
    missing = set(declared) - observed_entries
    if missing:
        raise ReleaseTreeError("release tree is missing declared files")

    for relative_path, record in declared.items():
        fd = -1
        try:
            fd, st = _open_declared_file(release_root, relative_path)
            if st.st_size != record["size"]:
                raise ReleaseTreeError("declared file size mismatch")
            if _sha256_fd(fd) != record["sha256"]:
                raise ReleaseTreeError("declared file digest mismatch")
        finally:
            if fd >= 0:
                os.close(fd)

    return {
        "release_id": verified_manifest["release_id"],
        "manifest_sha256": verified_manifest["manifest_sha256"],
        "file_count": len(declared),
    }
