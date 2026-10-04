"""FS04 isolated verified candidate staging; no activation or authority mutation."""

from __future__ import annotations
import ctypes, errno, os, shutil, stat, uuid
from pathlib import Path
from .release_manifest import ReleaseManifestError, validate_release_manifest
from .release_tree import ReleaseTreeError, verify_release_tree
from .release_store_guard import (
    ReleaseStoreGuardError,
    remove_private_stage,
    seal_private_stage,
    verify_published_release,
    verify_store_root,
)


class ReleaseStagingError(ValueError):
    """Raised when candidate staging cannot complete as an all-or-nothing operation."""


def _store_root(value: str | os.PathLike[str]) -> Path:
    root = Path(value)
    if not root.is_absolute():
        raise ReleaseStagingError("release store root must be absolute")
    try:
        st = root.lstat()
    except OSError as exc:
        raise ReleaseStagingError("release store root unavailable") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise ReleaseStagingError("release store root must be real directory")
    return root


def _rename_noreplace(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ReleaseStagingError("atomic no-replace rename unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    rc = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if rc != 0:
        err = ctypes.get_errno()
        if err == errno.EEXIST:
            raise ReleaseStagingError("release destination already exists")
        raise ReleaseStagingError("atomic no-replace publication failed")


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _copy_declared(source: Path, temp: Path, manifest: dict) -> None:
    for record in manifest["files"]:
        rel = record["path"]
        src = source / rel
        dst = temp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        sfd = -1
        try:
            sfd = os.open(str(src), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            st = os.fstat(sfd)
            if not stat.S_ISREG(st.st_mode):
                raise ReleaseStagingError("source changed to non-regular file during staging")
            with dst.open("xb") as out:
                while True:
                    chunk = os.read(sfd, 1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                os.fchmod(out.fileno(), 0o700 if st.st_mode & 0o111 else 0o600)
                out.flush()
                os.fsync(out.fileno())
        except (OSError, FileExistsError) as exc:
            raise ReleaseStagingError("candidate file copy failed") from exc
        finally:
            if sfd >= 0:
                os.close(sfd)
    for current, dirs, _ in os.walk(temp, topdown=False):
        _fsync_dir(Path(current))


def stage_release(
    source_root: str | os.PathLike[str], manifest: object, store_root: str | os.PathLike[str]
) -> dict:
    try:
        verified = validate_release_manifest(manifest)
    except ReleaseManifestError as exc:
        raise ReleaseStagingError("invalid candidate manifest") from exc
    source = Path(source_root)
    try:
        verify_release_tree(source, verified)
    except (ReleaseTreeError, OSError) as exc:
        raise ReleaseStagingError("source candidate tree failed verification") from exc
    store = _store_root(store_root)
    try:
        store, store_dev = verify_store_root(store)
    except ReleaseStoreGuardError as exc:
        raise ReleaseStagingError("release store metadata invalid") from exc
    final = store / verified["release_id"]
    if final.exists() or final.is_symlink():
        raise ReleaseStagingError("release destination already exists")
    temp = store / (".stage-" + str(uuid.uuid4()))
    published = False
    try:
        temp.mkdir(mode=0o700)
        _copy_declared(source, temp, verified)
        try:
            result = verify_release_tree(temp, verified)
        except ReleaseTreeError as exc:
            raise ReleaseStagingError("staged candidate failed independent verification") from exc
        try:
            seal_private_stage(temp, store_dev)
        except ReleaseStoreGuardError as exc:
            raise ReleaseStagingError("staged candidate could not be sealed") from exc
        _rename_noreplace(temp, final)
        published = True
        _fsync_dir(store)
        try:
            verify_published_release(store, verified["release_id"])
        except ReleaseStoreGuardError as exc:
            raise ReleaseStagingError("published candidate metadata invalid") from exc
        return {
            "release_id": result["release_id"],
            "manifest_sha256": result["manifest_sha256"],
            "path": str(final),
            "file_count": result["file_count"],
        }
    except ReleaseStagingError:
        raise
    except OSError as exc:
        raise ReleaseStagingError("candidate staging transaction failed") from exc
    finally:
        if not published and temp.exists():
            try:
                remove_private_stage(temp)
            except ReleaseStoreGuardError:
                pass
