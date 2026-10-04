import hashlib
import os
import pathlib
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.process_preflight import ProcessPreflightError, verify_process_candidate


class F10ProcessPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.exe = self.root / "worker"
        self.exe.write_bytes(b"#!/bin/sh\nexit 0\n")
        self.exe.chmod(0o700)
        self.spec = {
            "version": "0.1",
            "executable": str(self.exe),
            "argv": [],
            "cwd": str(self.cwd),
            "env": {},
            "sha256": hashlib.sha256(self.exe.read_bytes()).hexdigest(),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_candidate(self):
        result = verify_process_candidate(self.spec)
        self.assertTrue(result["verified"])
        self.assertEqual(result["sha256"], self.spec["sha256"])

    def test_hash_mismatch_rejected(self):
        bad = dict(self.spec, sha256="0" * 64)
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(bad)

    def test_missing_executable_rejected(self):
        self.exe.unlink()
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(self.spec)

    def test_missing_cwd_rejected(self):
        self.cwd.rmdir()
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(self.spec)

    def test_executable_symlink_rejected(self):
        link = self.root / "worker-link"
        link.symlink_to(self.exe)
        spec = dict(self.spec, executable=str(link))
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(spec)

    def test_cwd_symlink_rejected(self):
        link = self.root / "work-link"
        link.symlink_to(self.cwd, target_is_directory=True)
        spec = dict(self.spec, cwd=str(link))
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(spec)

    def test_directory_as_executable_rejected(self):
        spec = dict(self.spec, executable=str(self.cwd))
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(spec)

    def test_file_as_cwd_rejected(self):
        spec = dict(self.spec, cwd=str(self.exe))
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(spec)

    def test_non_executable_file_rejected(self):
        self.exe.chmod(0o600)
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(self.spec)

    def test_group_writable_executable_rejected(self):
        self.exe.chmod(0o720)
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(self.spec)

    def test_world_writable_executable_rejected(self):
        self.exe.chmod(0o702)
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(self.spec)

    def test_invalid_process_spec_wrapped(self):
        bad = dict(self.spec, executable="relative")
        with self.assertRaises(ProcessPreflightError):
            verify_process_candidate(bad)

    def test_size_reported(self):
        self.assertEqual(verify_process_candidate(self.spec)["size"], len(self.exe.read_bytes()))


if __name__ == "__main__":
    unittest.main()
