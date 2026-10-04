"""FS06 deterministic recovery of authority/pointer disagreement and bad ACTIVE bytes."""

from __future__ import annotations
from pathlib import Path
from .release_activation import (
    ReleaseActivationError,
    _cleanup_switch_temps,
    _read_current,
    _real_dir,
    _switch,
)
from .release_manifest import ReleaseManifestError, validate_release_manifest
from .release_state import ReleaseStateError, read_release_state, rollback_to_lkg
from .release_tree import ReleaseTreeError, verify_release_tree
from .release_store_guard import ReleaseStoreGuardError, verify_published_release, verify_store_root


class ReleaseRecoveryError(ValueError):
    """Raised when safe deterministic recovery cannot be completed."""


def _resolve(identity: dict, manifests: object) -> dict:
    if not isinstance(manifests, dict):
        raise ReleaseRecoveryError("manifest registry object required")
    rid = identity["release_id"]
    if rid not in manifests:
        raise ReleaseRecoveryError("required release manifest missing")
    try:
        manifest = validate_release_manifest(manifests[rid])
    except ReleaseManifestError as exc:
        raise ReleaseRecoveryError("required release manifest invalid") from exc
    observed = {
        "release_id": manifest["release_id"],
        "manifest_sha256": manifest["manifest_sha256"],
    }
    if observed != identity:
        raise ReleaseRecoveryError("manifest identity disagrees with authority state")
    return manifest


def _tree_ok(store: Path, identity: dict, manifests: object) -> bool:
    try:
        manifest = _resolve(identity, manifests)
        release = verify_published_release(store, identity["release_id"])
        verify_release_tree(release, manifest)
        return True
    except (ReleaseRecoveryError, ReleaseStoreGuardError, ReleaseTreeError, OSError):
        return False


def reconcile_release(store_root, pointer_dir, state_dir, manifests: object) -> dict:
    try:
        state = read_release_state(state_dir)
    except ReleaseStateError as exc:
        raise ReleaseRecoveryError("authoritative release state invalid") from exc
    try:
        store = _real_dir(store_root, "release store")
        pointers = _real_dir(pointer_dir, "pointer directory")
        verify_store_root(store)
        _cleanup_switch_temps(pointers)
    except (ReleaseActivationError, ReleaseStoreGuardError) as exc:
        raise ReleaseRecoveryError("release recovery directories invalid") from exc
    active = state["active"]
    lkg = state["last_known_good"]
    if _tree_ok(store, active, manifests):
        try:
            current = _read_current(pointers)
        except ReleaseActivationError:
            current = None
        if current != active["release_id"]:
            try:
                _switch(pointers, active["release_id"])
            except ReleaseActivationError as exc:
                raise ReleaseRecoveryError(
                    "verified ACTIVE could not repair current pointer"
                ) from exc
            return {"action": "RESTORED_ACTIVE_POINTER", "state": read_release_state(state_dir)}
        return {"action": "NO_ACTION", "state": state}
    if lkg == active or not _tree_ok(store, lkg, manifests):
        raise ReleaseRecoveryError("no verified authoritative ACTIVE or distinct LKG available")
    try:
        rolled = rollback_to_lkg(state_dir)
    except ReleaseStateError as exc:
        raise ReleaseRecoveryError("LKG authority rollback commit failed") from exc
    try:
        _switch(pointers, lkg["release_id"])
    except ReleaseActivationError as exc:
        raise ReleaseRecoveryError(
            "LKG authority committed but current pointer repair failed"
        ) from exc
    return {"action": "ROLLED_BACK_TO_LKG", "state": rolled}
