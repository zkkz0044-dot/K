import hashlib
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.managed_process import launch_managed
from kk_f.replacement_supervisor import ReplacementSupervisorError, evaluate_and_replace
from kk_f.restart_ledger import initialize, read_ledger


class F14ReplacementSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.ledger = self.root / "ledger"
        self.exe = self.root / "worker.py"
        self.exe.write_text(
            "#!/usr/bin/python3\n"
            "import pathlib,sys,time\n"
            "if '--mark' in sys.argv: pathlib.Path('replacement-started').write_text('yes')\n"
            "if '--fail7' in sys.argv: raise SystemExit(7)\n"
            "time.sleep(5)\n"
        )
        self.exe.chmod(0o700)
        self.handles = []

    def tearDown(self):
        for handle in self.handles:
            try:
                handle.stop(grace_seconds=0.05)
            except Exception:
                pass
        self.tmp.cleanup()

    def spec(self, argv=None):
        return {
            "version": "0.1",
            "executable": str(self.exe),
            "argv": list(argv or []),
            "cwd": str(self.cwd),
            "env": {},
            "sha256": hashlib.sha256(self.exe.read_bytes()).hexdigest(),
        }

    def launch(self, argv=None):
        handle = launch_managed(self.spec(argv))
        self.handles.append(handle)
        return handle

    def wait_status(self, handle, expected, timeout=1.0):
        deadline = time.monotonic() + timeout
        observed = handle.observe()
        while observed["status"] != expected and time.monotonic() < deadline:
            time.sleep(0.01)
            observed = handle.observe()
        self.assertEqual(observed["status"], expected)
        return observed

    def test_running_process_is_not_replaced_and_budget_not_consumed(self):
        initialize(str(self.ledger), 2)
        current = self.launch()
        result = evaluate_and_replace(str(self.ledger), current, self.spec(["--mark"]))
        self.assertEqual(result.observed_status, "RUNNING")
        self.assertEqual(result.decision, "NO_ACTION")
        self.assertIsNone(result.replacement)
        self.assertEqual(result.attempts, 0)
        self.assertFalse((self.cwd / "replacement-started").exists())

    def test_failed_process_consumes_one_attempt_and_launches_replacement(self):
        initialize(str(self.ledger), 2)
        current = self.launch(["--fail7"])
        self.wait_status(current, "FAILED")
        result = evaluate_and_replace(str(self.ledger), current, self.spec(["--mark"]))
        self.assertEqual(result.observed_status, "FAILED")
        self.assertEqual(result.decision, "REPLACE_INSTANCE")
        self.assertEqual(result.attempts, 1)
        self.assertIsNotNone(result.replacement)
        self.handles.append(result.replacement)
        deadline = time.monotonic() + 1.0
        marker = self.cwd / "replacement-started"
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists())
        self.assertEqual(read_ledger(str(self.ledger))["attempts"], 1)

    def test_cleanly_stopped_process_is_not_replaced(self):
        initialize(str(self.ledger), 2)
        self.exe.write_text("#!/usr/bin/python3\nraise SystemExit(0)\n")
        self.exe.chmod(0o700)
        current = self.launch()
        self.wait_status(current, "STOPPED")
        result = evaluate_and_replace(str(self.ledger), current, self.spec())
        self.assertEqual(result.decision, "NO_ACTION")
        self.assertIsNone(result.replacement)
        self.assertEqual(result.attempts, 0)

    def test_budget_exhaustion_holds_failed_without_launch(self):
        initialize(str(self.ledger), 1)
        first = self.launch(["--fail7"])
        self.wait_status(first, "FAILED")
        first_result = evaluate_and_replace(str(self.ledger), first, self.spec(["--fail7"]))
        self.assertEqual(first_result.decision, "REPLACE_INSTANCE")
        self.handles.append(first_result.replacement)
        self.wait_status(first_result.replacement, "FAILED")
        marker = self.cwd / "replacement-started"
        if marker.exists():
            marker.unlink()
        held = evaluate_and_replace(str(self.ledger), first_result.replacement, self.spec(["--mark"]))
        self.assertEqual(held.decision, "HOLD_FAILED")
        self.assertEqual(held.attempts, 1)
        self.assertIsNone(held.replacement)
        self.assertFalse(marker.exists())

    def test_corrupt_ledger_blocks_replacement(self):
        initialize(str(self.ledger), 2)
        current = self.launch(["--fail7"])
        self.wait_status(current, "FAILED")
        (self.ledger / "checkpoint.json").write_text("corrupt\n")
        with self.assertRaises(ReplacementSupervisorError):
            evaluate_and_replace(str(self.ledger), current, self.spec(["--mark"]))
        self.assertFalse((self.cwd / "replacement-started").exists())

    def test_hash_mutation_blocks_launch_but_consumes_approved_attempt(self):
        initialize(str(self.ledger), 2)
        current = self.launch(["--fail7"])
        self.wait_status(current, "FAILED")
        replacement_spec = self.spec(["--mark"])
        self.exe.write_text(self.exe.read_text() + "# mutation\n")
        with self.assertRaises(ReplacementSupervisorError):
            evaluate_and_replace(str(self.ledger), current, replacement_spec)
        ledger = read_ledger(str(self.ledger))
        self.assertEqual(ledger["attempts"], 1)
        self.assertEqual(ledger["last_decision"], "REPLACE_INSTANCE")
        self.assertFalse((self.cwd / "replacement-started").exists())

    def test_invalid_current_type_rejected_before_ledger_mutation(self):
        initialize(str(self.ledger), 2)
        before = read_ledger(str(self.ledger))
        with self.assertRaises(ReplacementSupervisorError):
            evaluate_and_replace(str(self.ledger), object(), self.spec())
        self.assertEqual(read_ledger(str(self.ledger)), before)

    def test_repeated_failures_never_exceed_budget(self):
        initialize(str(self.ledger), 2)
        current = self.launch(["--fail7"])
        self.wait_status(current, "FAILED")
        one = evaluate_and_replace(str(self.ledger), current, self.spec(["--fail7"]))
        self.handles.append(one.replacement)
        self.wait_status(one.replacement, "FAILED")
        two = evaluate_and_replace(str(self.ledger), one.replacement, self.spec(["--fail7"]))
        self.handles.append(two.replacement)
        self.wait_status(two.replacement, "FAILED")
        three = evaluate_and_replace(str(self.ledger), two.replacement, self.spec(["--mark"]))
        self.assertEqual((one.attempts, two.attempts, three.attempts), (1, 2, 2))
        self.assertEqual(three.decision, "HOLD_FAILED")
        self.assertIsNone(three.replacement)


if __name__ == "__main__":
    unittest.main()
