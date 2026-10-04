from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from kk_f.release_tree import ReleaseTreeError, verify_release_tree


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def manifest_for(files):
    records = []
    for path, data in sorted(files.items()):
        records.append({"path": path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    value = {
        "version": "0.1",
        "release_id": "12345678-1234-5678-9234-567812345678",
        "entrypoint": "kk_f/main.py",
        "files": records,
        "manifest_sha256": "",
    }
    material = {key: value[key] for key in ("version", "release_id", "entrypoint", "files")}
    value["manifest_sha256"] = hashlib.sha256(canonical(material)).hexdigest()
    return value


class ReleaseTreeTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name) / "release"
        self.root.mkdir()
        self.files = {"kk_f/__init__.py": b"", "kk_f/main.py": b"print('ok')\n"}
        for relative, data in self.files.items():
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        self.manifest = manifest_for(self.files)

    def tearDown(self):
        self.td.cleanup()

    def test_exact_tree_passes_and_returns_identity(self):
        result = verify_release_tree(self.root, self.manifest)
        self.assertEqual(result["release_id"], self.manifest["release_id"])
        self.assertEqual(result["manifest_sha256"], self.manifest["manifest_sha256"])
        self.assertEqual(result["file_count"], 2)

    def test_relative_root_rejected(self):
        with self.assertRaises(ReleaseTreeError): verify_release_tree("relative", self.manifest)

    def test_symlink_root_rejected(self):
        link = Path(self.td.name) / "link"; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ReleaseTreeError): verify_release_tree(link, self.manifest)

    def test_missing_file_rejected(self):
        (self.root / "kk_f/main.py").unlink()
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_changed_bytes_same_size_rejected(self):
        (self.root / "kk_f/main.py").write_bytes(b"print('NO')\n")
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_changed_size_rejected(self):
        (self.root / "kk_f/main.py").write_bytes(b"x")
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_undeclared_file_rejected(self):
        (self.root / "extra.txt").write_text("x")
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_undeclared_symlink_rejected(self):
        (self.root / "extra-link").symlink_to(self.root / "kk_f/main.py")
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_declared_file_replaced_by_symlink_rejected(self):
        target = Path(self.td.name) / "outside"; target.write_bytes(self.files["kk_f/main.py"])
        path = self.root / "kk_f/main.py"; path.unlink(); path.symlink_to(target)
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_symlinked_parent_directory_rejected(self):
        outside = Path(self.td.name) / "outside-dir"; outside.mkdir(); (outside / "main.py").write_bytes(self.files["kk_f/main.py"])
        package = self.root / "kk_f"
        for child in package.iterdir(): child.unlink()
        package.rmdir(); package.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_fifo_substitution_rejected(self):
        path = self.root / "kk_f/main.py"; path.unlink(); os.mkfifo(path)
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, self.manifest)

    def test_invalid_manifest_rejected_before_tree_credit(self):
        bad = dict(self.manifest); bad["manifest_sha256"] = "0" * 64
        with self.assertRaises(ReleaseTreeError): verify_release_tree(self.root, bad)

    def test_undeclared_empty_directory_rejected(self):
        (self.root / "empty").mkdir()
        with self.assertRaises(ReleaseTreeError):
            verify_release_tree(self.root, self.manifest)

    def test_verification_is_read_only(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        verify_release_tree(self.root, self.manifest)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__": unittest.main()
