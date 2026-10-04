from __future__ import annotations

import hashlib
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from kk_f.frozen_authority import build_frozen_authority, FrozenAuthorityError, load_frozen_authority
from kk_f.launch_guard import LaunchGuardError, open_verified_launch
from kk_f.path_guard import PathGuardError, open_absolute_dir, open_absolute_file
from kk_f.production_daemon import ProductionDaemonError, load_runtime_config


class FH02PathGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.real = self.root / "real"
        self.real.mkdir()
        self.cwd = self.real / "work"; self.cwd.mkdir()
        self.exe = self.real / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\n")
        self.exe.chmod(0o700)
        self.digest = hashlib.sha256(self.exe.read_bytes()).hexdigest()
        self.auth = self.real / "authority.json"
        self.manifest = build_frozen_authority('fh02-root', self.spec(), 2)
        self.auth.write_text(json.dumps(self.manifest,separators=(",",":"))+"\n"); self.auth.chmod(0o600)
        self.config = self.real / "runtime.json"
        self.config_value = {
            "version":"0.1","authority_path":str(self.auth),"ledger_directory":str(self.real/"ledger"),
            "evidence_directory":str(self.real/"evidence"),"heartbeat_path":str(self.real/"heartbeat.json"),
            "process_spec":{"version":"0.1","executable":str(self.exe),"argv":[],"cwd":str(self.cwd),"env":{},"sha256":self.digest},
            "healthy_within_seconds":1,"degraded_within_seconds":2,"grace_seconds":0.1,
            "base_delay_seconds":0.1,"max_delay_seconds":1.0,"poll_interval_seconds":0.1,"heartbeat_startup_grace_seconds":1.0,
        }
        self.config.write_text(json.dumps(self.config_value,separators=(",",":"))+"\n"); self.config.chmod(0o600)

    def tearDown(self): self.tmp.cleanup()

    def spec(self, executable=None, cwd=None):
        return {"version":"0.1","executable":str(executable or self.exe),"argv":[],"cwd":str(cwd or self.cwd),"env":{},"sha256":self.digest}

    def test_canonical_path_ambiguity_rejected(self):
        for bad in ("relative", str(self.real)+"/", str(self.root)+"//real", str(self.root)+"/real/../real"):
            with self.assertRaises(PathGuardError, msg=bad): open_absolute_dir(bad)

    def test_parent_symlink_executable_rejected(self):
        link = self.root / "parent-link"; link.symlink_to(self.real, target_is_directory=True)
        with self.assertRaises(LaunchGuardError): open_verified_launch(self.spec(executable=link/"worker.py"))

    def test_parent_symlink_cwd_rejected(self):
        link = self.root / "parent-link"; link.symlink_to(self.real, target_is_directory=True)
        with self.assertRaises(LaunchGuardError): open_verified_launch(self.spec(cwd=link/"work"))

    def test_parent_symlink_authority_rejected(self):
        link = self.root / "parent-link"; link.symlink_to(self.real, target_is_directory=True)
        with self.assertRaises(FrozenAuthorityError): load_frozen_authority(str(link/"authority.json"))

    def test_parent_symlink_runtime_config_rejected(self):
        link = self.root / "parent-link"; link.symlink_to(self.real, target_is_directory=True)
        with self.assertRaises(ProductionDaemonError): load_runtime_config(str(link/"runtime.json"))

    def test_authority_path_swap_after_open_reads_original_fd(self):
        import kk_f.frozen_authority as mod
        real_read = mod.read_all_fd
        def raced(fd, *, max_bytes):
            old = self.real / "authority-old.json"; self.auth.rename(old)
            malicious = dict(self.manifest, authority_id="attacker")
            self.auth.write_text(json.dumps(malicious,separators=(",",":"))+"\n"); self.auth.chmod(0o600)
            return real_read(fd, max_bytes=max_bytes)
        with mock.patch("kk_f.frozen_authority.read_all_fd", side_effect=raced):
            result = load_frozen_authority(str(self.auth))
        self.assertEqual(result["authority_id"], "fh02-root")

    def test_runtime_config_path_swap_after_open_reads_original_fd(self):
        import kk_f.production_daemon as mod
        real_read = mod.read_all_fd
        def raced(fd, *, max_bytes):
            old = self.real / "runtime-old.json"; self.config.rename(old)
            malicious = dict(self.config_value, healthy_within_seconds=999)
            self.config.write_text(json.dumps(malicious,separators=(",",":"))+"\n"); self.config.chmod(0o600)
            return real_read(fd, max_bytes=max_bytes)
        with mock.patch("kk_f.production_daemon.read_all_fd", side_effect=raced):
            cfg = load_runtime_config(str(self.config))
        self.assertEqual(cfg.healthy_within_seconds, 1)

    def test_final_file_symlink_rejected_by_path_guard(self):
        link = self.root / "auth-link"; link.symlink_to(self.auth)
        with self.assertRaises(PathGuardError): open_absolute_file(str(link))

    def test_repeated_parent_symlink_rejections_do_not_leak_fds(self):
        link = self.root / "parent-link"; link.symlink_to(self.real, target_is_directory=True)
        before = len(os.listdir("/proc/self/fd"))
        for _ in range(300):
            with self.assertRaises(PathGuardError): open_absolute_file(str(link/"authority.json"))
        after = len(os.listdir("/proc/self/fd"))
        self.assertLessEqual(after, before + 1)


if __name__ == "__main__": unittest.main()
