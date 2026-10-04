import hashlib
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.process_executor import ProcessExecutionError, execute_and_wait


class F11ProcessExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.exe = self.root / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\nimport os,sys,time\nprint(os.getcwd())\nprint(os.environ.get('F11_VALUE',''))\nprint('|'.join(sys.argv[1:]))\nif '--sleep' in sys.argv: time.sleep(2)\nif '--err' in sys.argv: print('ERR', file=sys.stderr)\nif '--exit7' in sys.argv: raise SystemExit(7)\n")
        self.exe.chmod(0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, argv=None, env=None):
        data = self.exe.read_bytes()
        return {
            "version": "0.1",
            "executable": str(self.exe),
            "argv": list(argv or []),
            "cwd": str(self.cwd),
            "env": dict(env or {}),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def test_direct_execution_success(self):
        result = execute_and_wait(self.spec(), timeout_seconds=1)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["exit_code"], 0)

    def test_exact_cwd_used(self):
        result = execute_and_wait(self.spec(), timeout_seconds=1)
        self.assertIn(str(self.cwd).encode(), result["stdout"])

    def test_explicit_environment_used(self):
        result = execute_and_wait(self.spec(env={"F11_VALUE": "exact"}), timeout_seconds=1)
        self.assertIn(b"exact", result["stdout"])

    def test_shell_metacharacters_are_literal_argv(self):
        marker = self.root / "pwned"
        arg = ";touch " + str(marker)
        result = execute_and_wait(self.spec(argv=[arg]), timeout_seconds=1)
        self.assertIn(arg.encode(), result["stdout"])
        self.assertFalse(marker.exists())

    def test_nonzero_exit_is_reported_not_hidden(self):
        result = execute_and_wait(self.spec(argv=["--exit7"]), timeout_seconds=1)
        self.assertEqual(result["exit_code"], 7)
        self.assertFalse(result["timed_out"])

    def test_stderr_is_captured(self):
        result = execute_and_wait(self.spec(argv=["--err"]), timeout_seconds=1)
        self.assertIn(b"ERR", result["stderr"])

    def test_timeout_kills_and_reports(self):
        result = execute_and_wait(self.spec(argv=["--sleep"]), timeout_seconds=0.05)
        self.assertTrue(result["timed_out"])
        self.assertIsNotNone(result["exit_code"])

    def test_hash_change_blocks_launch(self):
        spec = self.spec()
        self.exe.write_text(self.exe.read_text() + "# changed\n")
        with self.assertRaises(ProcessExecutionError):
            execute_and_wait(spec, timeout_seconds=1)

    def test_relative_spec_blocks_launch(self):
        spec = self.spec()
        spec["executable"] = "relative"
        with self.assertRaises(ProcessExecutionError):
            execute_and_wait(spec, timeout_seconds=1)

    def test_zero_timeout_rejected_before_launch(self):
        with self.assertRaises(ProcessExecutionError):
            execute_and_wait(self.spec(), timeout_seconds=0)

    def test_bool_timeout_rejected(self):
        with self.assertRaises(ProcessExecutionError):
            execute_and_wait(self.spec(), timeout_seconds=True)

    def test_negative_timeout_rejected(self):
        with self.assertRaises(ProcessExecutionError):
            execute_and_wait(self.spec(), timeout_seconds=-1)

    def test_verified_digest_reported(self):
        spec = self.spec()
        result = execute_and_wait(spec, timeout_seconds=1)
        self.assertEqual(result["verified_sha256"], spec["sha256"])

    def test_pid_is_positive_integer(self):
        result = execute_and_wait(self.spec(), timeout_seconds=1)
        self.assertIs(type(result["pid"]), int)
        self.assertGreater(result["pid"], 0)


if __name__ == "__main__":
    unittest.main()
