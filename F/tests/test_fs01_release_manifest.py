from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kk_f.release_manifest import (
    ReleaseManifestError,
    load_release_manifest,
    manifest_sha256,
    validate_release_manifest,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def valid_manifest():
    value = {
        "version": "0.1",
        "release_id": "12345678-1234-5678-9234-567812345678",
        "entrypoint": "kk_f/production_daemon.py",
        "files": [
            {"path": "kk_f/__init__.py", "sha256": "1" * 64, "size": 0},
            {"path": "kk_f/production_daemon.py", "sha256": "a" * 64, "size": 123},
        ],
        "manifest_sha256": "",
    }
    material = {key: value[key] for key in ("version", "release_id", "entrypoint", "files")}
    value["manifest_sha256"] = hashlib.sha256(canonical(material)).hexdigest()
    return value


class ReleaseManifestTests(unittest.TestCase):
    def test_valid_manifest_and_identity(self):
        value = valid_manifest()
        self.assertEqual(validate_release_manifest(value), value)
        self.assertEqual(manifest_sha256(value), value["manifest_sha256"])

    def test_exact_top_level_schema(self):
        for mutation in ("missing", "extra"):
            value = valid_manifest()
            if mutation == "missing":
                del value["entrypoint"]
            else:
                value["extra"] = 1
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_exact_file_schema(self):
        value = valid_manifest()
        value["files"][0]["extra"] = 1
        with self.assertRaises(ReleaseManifestError):
            validate_release_manifest(value)

    def test_version_is_frozen(self):
        value = valid_manifest(); value["version"] = "0.2"
        with self.assertRaises(ReleaseManifestError):
            validate_release_manifest(value)

    def test_release_id_must_be_canonical_lowercase_uuid(self):
        for bad in (123, "not-a-uuid", "deadbeef-dead-4eef-8ead-deadbeefcafe".upper()):
            value = valid_manifest(); value["release_id"] = bad
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_paths_reject_ambiguity_and_traversal(self):
        bad_paths = ("", "/abs/file", "../escape", "a/../b", "./a", "a//b", "a\\b", "a\x00b")
        for bad in bad_paths:
            value = valid_manifest(); value["files"][0]["path"] = bad
            with self.assertRaises(ReleaseManifestError, msg=repr(bad)):
                validate_release_manifest(value)

    def test_entrypoint_path_is_strict(self):
        for bad in ("/kk_f/production_daemon.py", "kk_f/../production_daemon.py", "kk_f\\production_daemon.py"):
            value = valid_manifest(); value["entrypoint"] = bad
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_files_must_be_nonempty_list(self):
        for bad in ([], {}, "x", None):
            value = valid_manifest(); value["files"] = bad
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_files_must_be_sorted(self):
        value = valid_manifest(); value["files"] = list(reversed(value["files"]))
        with self.assertRaises(ReleaseManifestError):
            validate_release_manifest(value)

    def test_file_paths_must_be_unique(self):
        value = valid_manifest(); value["files"][1]["path"] = value["files"][0]["path"]
        with self.assertRaises(ReleaseManifestError):
            validate_release_manifest(value)

    def test_entrypoint_must_be_declared(self):
        value = valid_manifest(); value["entrypoint"] = "kk_f/missing.py"
        with self.assertRaises(ReleaseManifestError):
            validate_release_manifest(value)

    def test_sha256_fields_are_strict_lowercase_hex(self):
        for bad in ("A" * 64, "g" * 64, "a" * 63, 7):
            value = valid_manifest(); value["files"][0]["sha256"] = bad
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_size_is_strict_nonnegative_integer(self):
        for bad in (-1, True, 1.5, "1"):
            value = valid_manifest(); value["files"][0]["size"] = bad
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_checksum_tampering_is_detected(self):
        value = valid_manifest(); value["files"][1]["size"] += 1
        with self.assertRaises(ReleaseManifestError):
            validate_release_manifest(value)

    def test_checksum_format_is_strict(self):
        for bad in ("A" * 64, "x" * 64, "0" * 63, None):
            value = valid_manifest(); value["manifest_sha256"] = bad
            with self.assertRaises(ReleaseManifestError):
                validate_release_manifest(value)

    def test_duplicate_json_keys_rejected(self):
        raw = '{"version":"0.1","version":"0.1"}'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "release.json"; path.write_text(raw)
            with self.assertRaises(ReleaseManifestError):
                load_release_manifest(path)

    def test_nonfinite_json_rejected(self):
        raw = '{"version":NaN}'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "release.json"; path.write_text(raw)
            with self.assertRaises(ReleaseManifestError):
                load_release_manifest(path)

    def test_invalid_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "release.json"; path.write_bytes(b"\xff\xfe")
            with self.assertRaises(ReleaseManifestError):
                load_release_manifest(path)

    def test_load_is_read_only(self):
        value = valid_manifest()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "release.json"
            raw = canonical(value) + b"\n"; path.write_bytes(raw)
            before = path.read_bytes()
            self.assertEqual(load_release_manifest(path), value)
            self.assertEqual(path.read_bytes(), before)

    def test_validation_does_not_mutate_input(self):
        value = valid_manifest(); before = copy.deepcopy(value)
        validate_release_manifest(value)
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()
