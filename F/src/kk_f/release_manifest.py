"""FS01 strict immutable release-manifest validation; read-only, no activation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path, PurePosixPath
from typing import Any
from .input_guard import InputGuardError, read_bounded_text

MANIFEST_VERSION = "0.1"
MANIFEST_KEYS = frozenset({"version", "release_id", "entrypoint", "files", "manifest_sha256"})
FILE_KEYS = frozenset({"path", "sha256", "size"})
HASH_KEYS = ("version", "release_id", "entrypoint", "files")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_FILES = 4096
MAX_RELATIVE_PATH_CHARS = 4096
MAX_FILE_SIZE = (1 << 63) - 1


class ReleaseManifestError(ValueError):
    """Raised when a release manifest is ambiguous, malformed, or corrupt."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReleaseManifestError("manifest value is not canonical finite JSON") from exc


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseManifestError("duplicate JSON key")
        result[key] = value
    return result


def _load_json(raw: str) -> dict:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ReleaseManifestError("non-finite number")
            ),
        )
    except ReleaseManifestError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise ReleaseManifestError("invalid release manifest JSON") from exc
    if not isinstance(value, dict):
        raise ReleaseManifestError("release manifest object required")
    return value


def _validate_release_id(value: object) -> str:
    if not isinstance(value, str):
        raise ReleaseManifestError("release_id string required")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ReleaseManifestError("release_id must be canonical UUID") from exc
    if str(parsed) != value:
        raise ReleaseManifestError("release_id must be canonical lowercase UUID")
    return value


def _validate_relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ReleaseManifestError(f"{label} must be a non-empty NUL-free string")
    if len(value) > MAX_RELATIVE_PATH_CHARS:
        raise ReleaseManifestError(f"{label} exceeds path length limit")
    if "\\" in value or "//" in value:
        raise ReleaseManifestError(f"{label} must be normalized POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ReleaseManifestError(f"{label} must be relative")
    parts = path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ReleaseManifestError(f"{label} must not contain dot traversal")
    normalized = path.as_posix()
    if normalized != value:
        raise ReleaseManifestError(f"{label} must be normalized POSIX path")
    return value


def _validate_file_record(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != FILE_KEYS:
        raise ReleaseManifestError("exact file-record keys required")
    path = _validate_relative_path(value["path"], "file path")
    digest = value["sha256"]
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        raise ReleaseManifestError("file sha256 must be lowercase 64-hex")
    size = value["size"]
    if type(size) is not int or size < 0 or size > MAX_FILE_SIZE:
        raise ReleaseManifestError("file size must be a bounded non-negative integer")
    return {"path": path, "sha256": digest, "size": size}


def _hash_material(value: dict) -> str:
    material = {key: value[key] for key in HASH_KEYS}
    return hashlib.sha256(_canonical_bytes(material)).hexdigest()


def validate_release_manifest(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != MANIFEST_KEYS:
        raise ReleaseManifestError("exact release-manifest keys required")
    if value["version"] != MANIFEST_VERSION:
        raise ReleaseManifestError("unsupported release manifest version")
    release_id = _validate_release_id(value["release_id"])
    entrypoint = _validate_relative_path(value["entrypoint"], "entrypoint")
    files_value = value["files"]
    if not isinstance(files_value, list) or not files_value:
        raise ReleaseManifestError("files must be a non-empty list")
    if len(files_value) > MAX_FILES:
        raise ReleaseManifestError("files exceeds count limit")
    files = [_validate_file_record(item) for item in files_value]
    paths = [item["path"] for item in files]
    if paths != sorted(paths):
        raise ReleaseManifestError("file records must be lexicographically sorted by path")
    if len(paths) != len(set(paths)):
        raise ReleaseManifestError("file paths must be unique")
    if entrypoint not in set(paths):
        raise ReleaseManifestError("entrypoint must be declared in files")
    checksum = value["manifest_sha256"]
    if not isinstance(checksum, str) or _SHA256_RE.fullmatch(checksum) is None:
        raise ReleaseManifestError("manifest_sha256 must be lowercase 64-hex")
    normalized = {
        "version": MANIFEST_VERSION,
        "release_id": release_id,
        "entrypoint": entrypoint,
        "files": files,
        "manifest_sha256": checksum,
    }
    if checksum != _hash_material(normalized):
        raise ReleaseManifestError("release manifest integrity mismatch")
    return normalized


def load_release_manifest(path: str | os.PathLike[str]) -> dict:
    manifest_path = Path(path)
    try:
        raw = read_bounded_text(manifest_path, max_bytes=1024 * 1024)
    except InputGuardError as exc:
        raise ReleaseManifestError("release manifest unreadable or too large") from exc
    return validate_release_manifest(_load_json(raw))


def manifest_sha256(value: object) -> str:
    """Return the verified manifest identity; invalid input fails closed."""
    return validate_release_manifest(value)["manifest_sha256"]
