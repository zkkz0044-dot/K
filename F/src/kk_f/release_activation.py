"""FS05 atomic current-pointer activation with durable authority commit."""

from __future__ import annotations
import os, stat, uuid
from pathlib import Path
from .release_manifest import ReleaseManifestError, validate_release_manifest
from .release_tree import ReleaseTreeError, verify_release_tree
from .release_state import ReleaseStateError, commit_candidate, read_release_state
from .release_store_guard import ReleaseStoreGuardError, verify_published_release, verify_store_root


class ReleaseActivationError(ValueError):
    """Raised when activation cannot complete or restore safely."""


def _real_dir(value, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ReleaseActivationError(f"{label} must be absolute")
    try:
        st = path.lstat()
    except OSError as exc:
        raise ReleaseActivationError(f"{label} unavailable") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise ReleaseActivationError(f"{label} must be real directory")
    return path


def _validate_release_id(value: object) -> str:
    if not isinstance(value, str):
        raise ReleaseActivationError("release_id string required")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ReleaseActivationError("release_id is not canonical UUID") from exc
    if str(parsed) != value:
        raise ReleaseActivationError("release_id is not canonical lowercase UUID")
    return value


def _identity(manifest: dict) -> dict:
    return {"release_id": manifest["release_id"], "manifest_sha256": manifest["manifest_sha256"]}


def _read_current(pointer_dir: Path) -> str:
    path = pointer_dir / "current"
    try:
        st = path.lstat()
        if not stat.S_ISLNK(st.st_mode):
            raise ReleaseActivationError("current must be symlink")
        target = os.readlink(path)
    except OSError as exc:
        raise ReleaseActivationError("current pointer unavailable") from exc
    if not target or "/" in target or "\\" in target or target in (".", ".."):
        raise ReleaseActivationError("current target must be one relative release_id")
    try:
        parsed = uuid.UUID(target)
    except ValueError as exc:
        raise ReleaseActivationError("current target is not canonical release_id") from exc
    if str(parsed) != target:
        raise ReleaseActivationError("current target is not canonical release_id")
    return target


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _cleanup_switch_temps(pointer_dir: Path) -> None:
    try:
        entries = list(pointer_dir.iterdir())
    except OSError as exc:
        raise ReleaseActivationError("pointer temp recovery scan failed") from exc
    removed = False
    for entry in entries:
        if not entry.name.startswith(".current-"):
            continue
        suffix = entry.name[len(".current-") :]
        try:
            parsed = uuid.UUID(suffix)
        except ValueError:
            continue
        if str(parsed) != suffix:
            continue
        try:
            if entry.is_dir() and not entry.is_symlink():
                raise ReleaseActivationError("pointer temp recovery found directory")
            entry.unlink()
            removed = True
        except ReleaseActivationError:
            raise
        except OSError as exc:
            raise ReleaseActivationError("pointer temp recovery cleanup failed") from exc
    if removed:
        _fsync_dir(pointer_dir)


def _switch(pointer_dir: Path, release_id: str) -> None:
    _cleanup_switch_temps(pointer_dir)
    temp = pointer_dir / (".current-" + str(uuid.uuid4()))
    try:
        os.symlink(release_id, temp)
        os.replace(temp, pointer_dir / "current")
        _fsync_dir(pointer_dir)
    except OSError as exc:
        raise ReleaseActivationError("atomic current-pointer switch failed") from exc
    finally:
        try:
            if temp.is_symlink() or temp.exists():
                temp.unlink()
        except OSError:
            pass


def initialize_current(pointer_dir, release_id: str) -> None:
    release_id = _validate_release_id(release_id)
    root = _real_dir(pointer_dir, "pointer directory")
    path = root / "current"
    if path.exists() or path.is_symlink():
        raise ReleaseActivationError("current already exists")
    _switch(root, release_id)


def activate_candidate(store_root, pointer_dir, state_dir, manifest: object) -> dict:
    try:
        verified = validate_release_manifest(manifest)
    except ReleaseManifestError as exc:
        raise ReleaseActivationError("invalid candidate manifest") from exc
    store = _real_dir(store_root, "release store")
    pointers = _real_dir(pointer_dir, "pointer directory")
    try:
        verify_store_root(store)
    except ReleaseStoreGuardError as exc:
        raise ReleaseActivationError("release store metadata invalid") from exc
    try:
        state = read_release_state(state_dir)
    except ReleaseStateError as exc:
        raise ReleaseActivationError("release authority state invalid") from exc
    candidate = _identity(verified)
    if state["candidate"] != candidate:
        raise ReleaseActivationError("manifest does not match authoritative candidate")
    if state["active"] == candidate:
        raise ReleaseActivationError("candidate already active")
    old_active = state["active"]["release_id"]
    if _read_current(pointers) != old_active:
        raise ReleaseActivationError("current pointer disagrees with authoritative ACTIVE")
    try:
        release_path = verify_published_release(store, verified["release_id"])
        verify_release_tree(release_path, verified)
    except (ReleaseStoreGuardError, ReleaseTreeError, OSError) as exc:
        raise ReleaseActivationError("staged candidate failed pre-activation verification") from exc
    _switch(pointers, verified["release_id"])
    try:
        committed = commit_candidate(state_dir)
    except ReleaseStateError as exc:
        try:
            _switch(pointers, old_active)
        except ReleaseActivationError as rollback_exc:
            raise ReleaseActivationError(
                "state commit failed and current-pointer restoration failed"
            ) from rollback_exc
        raise ReleaseActivationError("state commit failed; current pointer restored") from exc
    if (
        committed["active"] != candidate
        or committed["last_known_good"]["release_id"] != old_active
        or committed["candidate"] is not None
    ):
        raise ReleaseActivationError("post-commit authority invariant failed")
    return committed
