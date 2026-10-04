import hashlib
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.health_supervisor import supervise_once
from kk_f.managed_process import launch_managed
from kk_f.restart_backoff import RestartBackoffError, evaluate_restart_backoff
from kk_f.restart_ledger import RestartLedgerError, evaluate_and_record, initialize, read_ledger


class FP03RestartBackoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.ledger = self.root / "ledger"
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.exe = self.root / "worker.py"
        self.exe.write_text(
            "#!/usr/bin/python3\n"
            "import sys,time\n"
            "if '--fail' in sys.argv: raise SystemExit(7)\n"
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

    def wait_failed(self, handle):
        deadline = time.monotonic() + 1
        while handle.observe()["status"] == "RUNNING" and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(handle.observe()["status"], "FAILED")

    def test_ledger_initializes_with_persistent_null_timestamp(self):
        initialize(str(self.ledger), 4)
        self.assertIsNone(read_ledger(str(self.ledger))["last_attempt_at"])

    def test_attempt_and_timestamp_commit_together(self):
        initialize(str(self.ledger), 4)
        value = evaluate_and_record(str(self.ledger), "FAILED", attempted_at="2026-09-04T10:00:00Z")
        reread = read_ledger(str(self.ledger))
        self.assertEqual(value["attempts"], 1)
        self.assertEqual(reread["attempts"], 1)
        self.assertEqual(reread["last_attempt_at"], "2026-09-04T10:00:00Z")

    def test_backoff_persists_across_fresh_read(self):
        initialize(str(self.ledger), 4)
        evaluate_and_record(str(self.ledger), "FAILED", attempted_at="2026-09-04T10:00:00Z")
        fresh = read_ledger(str(self.ledger))
        result = evaluate_restart_backoff(fresh, now="2026-09-04T10:00:04Z", base_delay_seconds=10, max_delay_seconds=60)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["remaining_seconds"], 6.0)

    def test_exponential_sequence_and_cap(self):
        for attempts, expected in [(1, 5.0), (2, 10.0), (3, 20.0), (4, 20.0), (8, 20.0)]:
            ledger = {"attempts": attempts, "last_attempt_at": "2026-09-04T10:00:00Z"}
            result = evaluate_restart_backoff(ledger, now="2026-09-04T10:00:00Z", base_delay_seconds=5, max_delay_seconds=20)
            self.assertEqual(result["delay_seconds"], expected)

    def test_exact_deadline_is_allowed(self):
        ledger = {"attempts": 2, "last_attempt_at": "2026-09-04T10:00:00Z"}
        result = evaluate_restart_backoff(ledger, now="2026-09-04T10:00:10Z", base_delay_seconds=5, max_delay_seconds=60)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["remaining_seconds"], 0.0)

    def test_time_regression_rejected(self):
        ledger = {"attempts": 1, "last_attempt_at": "2026-09-04T10:00:10Z"}
        with self.assertRaises(RestartBackoffError):
            evaluate_restart_backoff(ledger, now="2026-09-04T10:00:09Z", base_delay_seconds=5, max_delay_seconds=60)

    def test_early_retry_waits_without_ledger_mutation_or_launch(self):
        initialize(str(self.ledger), 3)
        first = self.launch(["--fail"])
        self.wait_failed(first)
        one = supervise_once(
            str(self.ledger), first, {"bad": True}, self.spec(["--fail"]),
            now="2026-09-04T10:00:00Z", healthy_within_seconds=15,
            degraded_within_seconds=30, grace_seconds=0.05,
            base_delay_seconds=10, max_delay_seconds=60,
        )
        self.assertIsNotNone(one.replacement)
        self.handles.append(one.replacement)
        self.wait_failed(one.replacement)
        before = read_ledger(str(self.ledger))
        two = supervise_once(
            str(self.ledger), one.replacement, {"bad": True}, self.spec(["--fail"]),
            now="2026-09-04T10:00:05Z", healthy_within_seconds=15,
            degraded_within_seconds=30, grace_seconds=0.05,
            base_delay_seconds=10, max_delay_seconds=60,
        )
        self.assertEqual(two.decision, "WAIT_BACKOFF")
        self.assertIsNone(two.replacement)
        self.assertEqual(read_ledger(str(self.ledger)), before)

    def test_retry_after_deadline_commits_second_timestamp_before_launch(self):
        initialize(str(self.ledger), 3)
        first = self.launch(["--fail"])
        self.wait_failed(first)
        one = supervise_once(
            str(self.ledger), first, {"bad": True}, self.spec(["--fail"]),
            now="2026-09-04T10:00:00Z", healthy_within_seconds=15,
            degraded_within_seconds=30, grace_seconds=0.05,
            base_delay_seconds=10, max_delay_seconds=60,
        )
        self.handles.append(one.replacement)
        self.wait_failed(one.replacement)
        two = supervise_once(
            str(self.ledger), one.replacement, {"bad": True}, self.spec(),
            now="2026-09-04T10:00:10Z", healthy_within_seconds=15,
            degraded_within_seconds=30, grace_seconds=0.05,
            base_delay_seconds=10, max_delay_seconds=60,
        )
        self.assertEqual(two.decision, "REPLACE_INSTANCE")
        self.assertIsNotNone(two.replacement)
        self.handles.append(two.replacement)
        ledger = read_ledger(str(self.ledger))
        self.assertEqual(ledger["attempts"], 2)
        self.assertEqual(ledger["last_attempt_at"], "2026-09-04T10:00:10Z")

    def test_invalid_attempt_timestamp_rejected_without_mutation(self):
        initialize(str(self.ledger), 3)
        before = read_ledger(str(self.ledger))
        with self.assertRaises(RestartLedgerError):
            evaluate_and_record(str(self.ledger), "FAILED", attempted_at="not-time")
        self.assertEqual(read_ledger(str(self.ledger)), before)

    def test_attempt_timestamp_rejected_for_nonreplacement_decision(self):
        initialize(str(self.ledger), 3)
        before = read_ledger(str(self.ledger))
        with self.assertRaises(RestartLedgerError):
            evaluate_and_record(str(self.ledger), "HEALTHY", attempted_at="2026-09-04T10:00:00Z")
        self.assertEqual(read_ledger(str(self.ledger)), before)


if __name__ == "__main__":
    unittest.main()
