import hashlib
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.managed_process import ManagedProcessError, launch_managed


class F13ManagedProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.exe = self.root / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\nimport os,signal,sys,time\nif '--write-env' in sys.argv: open('env.txt','w').write(os.environ.get('F13_VALUE',''))\nif '--exit7' in sys.argv: raise SystemExit(7)\nif '--ignore-term' in sys.argv: signal.signal(signal.SIGTERM, signal.SIG_IGN); open('term-ready','w').write('ready')\ntime.sleep(5)\n")
        self.exe.chmod(0o700)
        self.handles = []

    def tearDown(self):
        for handle in self.handles:
            try:
                handle.stop(grace_seconds=0.05)
            except Exception:
                pass
        self.tmp.cleanup()

    def spec(self, argv=None, env=None):
        return {
            "version": "0.1",
            "executable": str(self.exe),
            "argv": list(argv or []),
            "cwd": str(self.cwd),
            "env": dict(env or {}),
            "sha256": hashlib.sha256(self.exe.read_bytes()).hexdigest(),
        }

    def launch(self, argv=None, env=None):
        handle = launch_managed(self.spec(argv=argv, env=env))
        self.handles.append(handle)
        return handle


    def wait_not_running(self, handle, timeout=1.0):
        deadline = time.monotonic() + timeout
        observed = handle.observe()
        while observed["status"] == "RUNNING" and time.monotonic() < deadline:
            time.sleep(0.01)
            observed = handle.observe()
        return observed

    def test_launch_reports_running_not_healthy(self):
        handle = self.launch()
        observed = handle.observe()
        self.assertEqual(observed["status"], "RUNNING")
        self.assertNotEqual(observed["status"], "HEALTHY")

    def test_pid_positive(self):
        handle = self.launch()
        self.assertIs(type(handle.pid), int)
        self.assertGreater(handle.pid, 0)

    def test_verified_digest_retained(self):
        spec = self.spec()
        handle = launch_managed(spec)
        self.handles.append(handle)
        self.assertEqual(handle.verified_sha256, spec["sha256"])

    def test_explicit_environment_reaches_child(self):
        handle = self.launch(["--write-env"], {"F13_VALUE": "exact"})
        target = self.cwd / "env.txt"
        deadline = time.monotonic() + 1.0
        observed = None
        while time.monotonic() < deadline:
            if target.exists():
                observed = target.read_text()
                if observed == "exact":
                    break
            time.sleep(0.01)
        self.assertEqual(observed, "exact")

    def test_clean_exit_observes_stopped(self):
        self.exe.write_text("#!/usr/bin/python3\nraise SystemExit(0)\n")
        self.exe.chmod(0o700)
        handle = self.launch()
        observed = self.wait_not_running(handle)
        self.assertEqual(observed["status"], "STOPPED")

    def test_nonzero_exit_observes_failed(self):
        handle = self.launch(["--exit7"])
        observed = self.wait_not_running(handle)
        self.assertEqual(observed["status"], "FAILED")
        self.assertEqual(observed["exit_code"], 7)

    def test_graceful_stop_returns_stopped(self):
        handle = self.launch()
        result = handle.stop(grace_seconds=0.5)
        self.assertEqual(result["status"], "STOPPED")
        self.assertFalse(result["forced"])

    def test_forced_stop_after_ignored_term(self):
        handle = self.launch(["--ignore-term"])
        ready = self.cwd / "term-ready"
        deadline = time.monotonic() + 1.0
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), "child did not install SIGTERM handler before deadline")
        result = handle.stop(grace_seconds=0.05)
        self.assertEqual(result["status"], "STOPPED")
        self.assertTrue(result["forced"])

    def test_invalid_grace_rejected_without_stop(self):
        handle = self.launch()
        with self.assertRaises(ManagedProcessError):
            handle.stop(grace_seconds=0)
        self.assertEqual(handle.observe()["status"], "RUNNING")

    def test_hash_change_blocks_launch(self):
        spec = self.spec()
        self.exe.write_text(self.exe.read_text() + "# changed\n")
        with self.assertRaises(ManagedProcessError):
            launch_managed(spec)

    def test_shell_metacharacters_remain_literal(self):
        marker = self.root / "pwned"
        handle = self.launch([";touch", str(marker)])
        time.sleep(0.05)
        self.assertFalse(marker.exists())

    def test_stop_already_exited_is_idempotent_stopped(self):
        self.exe.write_text("#!/usr/bin/python3\nraise SystemExit(0)\n")
        self.exe.chmod(0o700)
        handle = self.launch()
        self.wait_not_running(handle)
        result = handle.stop(grace_seconds=0.1)
        self.assertEqual(result["status"], "STOPPED")
        self.assertFalse(result["forced"])


if __name__ == "__main__":
    unittest.main()
