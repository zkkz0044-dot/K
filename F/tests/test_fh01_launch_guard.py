from __future__ import annotations

import hashlib
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from kk_f.launch_guard import LaunchGuardError, open_verified_launch
from kk_f.process_executor import ProcessExecutionError, execute_and_wait


class FH01LaunchGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        (self.cwd / "token").write_text("GOOD")
        self.exe = self.root / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nprint(Path('token').read_text())\n")
        self.exe.chmod(0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self):
        return {
            "version": "0.1",
            "executable": str(self.exe),
            "argv": [],
            "cwd": str(self.cwd),
            "env": {},
            "sha256": hashlib.sha256(self.exe.read_bytes()).hexdigest(),
        }

    def test_opened_identity_reports_exact_inode_and_digest(self):
        verified = open_verified_launch(self.spec())
        try:
            st = self.exe.stat()
            self.assertEqual((verified.device, verified.inode), (st.st_dev, st.st_ino))
            self.assertEqual(verified.sha256, self.spec()["sha256"])
            self.assertEqual(os.fstat(verified.executable_fd).st_ino, st.st_ino)
        finally:
            verified.close()

    def test_hardlinked_executable_rejected(self):
        os.link(self.exe, self.root / "second-link")
        with self.assertRaises(LaunchGuardError):
            open_verified_launch(self.spec())

    def test_symlink_executable_rejected(self):
        link = self.root / "link.py"
        link.symlink_to(self.exe)
        spec = self.spec(); spec["executable"] = str(link)
        with self.assertRaises(LaunchGuardError):
            open_verified_launch(spec)

    def test_fifo_executable_rejected_without_blocking(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        spec = self.spec(); spec["executable"] = str(fifo); spec["sha256"] = "0" * 64
        with self.assertRaises(LaunchGuardError):
            open_verified_launch(spec)

    def test_group_world_writable_executable_rejected(self):
        self.exe.chmod(0o722)
        with self.assertRaises(LaunchGuardError):
            open_verified_launch(self.spec())

    def test_final_cwd_symlink_rejected(self):
        real = self.root / "realcwd"; real.mkdir()
        link = self.root / "cwdlink"; link.symlink_to(real, target_is_directory=True)
        spec = self.spec(); spec["cwd"] = str(link)
        with self.assertRaises(LaunchGuardError):
            open_verified_launch(spec)

    def test_in_place_change_during_hash_rejected(self):
        import kk_f.launch_guard as guard
        real_hash = guard._hash_fd
        def mutate(fd):
            digest = real_hash(fd)
            self.exe.write_text(self.exe.read_text() + "# changed during verification\n")
            return digest
        with mock.patch("kk_f.launch_guard._hash_fd", side_effect=mutate):
            with self.assertRaises(LaunchGuardError):
                open_verified_launch(self.spec())

    def test_path_swap_after_verification_executes_verified_inode(self):
        import kk_f.process_executor as executor
        real_popen = executor.subprocess.Popen
        spec = self.spec()
        def raced(*args, **kwargs):
            old = self.root / "verified-old.py"
            self.exe.rename(old)
            self.exe.write_text("#!/usr/bin/python3\nprint('BAD')\n")
            self.exe.chmod(0o700)
            return real_popen(*args, **kwargs)
        with mock.patch("kk_f.process_executor.subprocess.Popen", side_effect=raced):
            result = execute_and_wait(spec, timeout_seconds=2)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"].strip(), b"GOOD")

    def test_cwd_swap_after_verification_uses_verified_directory_inode(self):
        import kk_f.process_executor as executor
        real_popen = executor.subprocess.Popen
        spec = self.spec()
        def raced(*args, **kwargs):
            old = self.root / "verified-work"
            self.cwd.rename(old)
            self.cwd.mkdir()
            (self.cwd / "token").write_text("BAD")
            return real_popen(*args, **kwargs)
        with mock.patch("kk_f.process_executor.subprocess.Popen", side_effect=raced):
            result = execute_and_wait(spec, timeout_seconds=2)
        self.assertEqual(result["stdout"].strip(), b"GOOD")

    def test_repeated_rejections_do_not_leak_fds(self):
        before = len(os.listdir("/proc/self/fd"))
        self.exe.chmod(0o722)
        for _ in range(200):
            with self.assertRaises(LaunchGuardError):
                open_verified_launch(self.spec())
        after = len(os.listdir("/proc/self/fd"))
        self.assertLessEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()
