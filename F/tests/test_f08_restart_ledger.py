import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.restart_ledger import RestartLedgerError, evaluate_and_record, initialize, read_ledger


class F08RestartLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "ledger"

    def tearDown(self):
        self.tmp.cleanup()

    def test_initialize_roundtrip(self):
        initialize(str(self.root), 3)
        ledger = read_ledger(str(self.root))
        self.assertEqual(ledger["attempts"], 0)
        self.assertEqual(ledger["max_attempts"], 3)
        self.assertEqual(ledger["last_decision"], "NO_ACTION")

    def test_failed_consumes_budget(self):
        initialize(str(self.root), 3)
        first = evaluate_and_record(str(self.root), "FAILED")
        second = evaluate_and_record(str(self.root), "FAILED")
        self.assertEqual(first["attempts"], 1)
        self.assertEqual(second["attempts"], 2)
        self.assertEqual(second["last_decision"], "REPLACE_INSTANCE")

    def test_budget_exhaustion_holds_without_increment(self):
        initialize(str(self.root), 2)
        evaluate_and_record(str(self.root), "FAILED")
        evaluate_and_record(str(self.root), "FAILED")
        held = evaluate_and_record(str(self.root), "FAILED")
        self.assertEqual(held["attempts"], 2)
        self.assertEqual(held["last_decision"], "HOLD_FAILED")

    def test_nonfailed_does_not_consume_budget(self):
        initialize(str(self.root), 3)
        result = evaluate_and_record(str(self.root), "DEGRADED")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(result["last_decision"], "NO_ACTION")

    def test_generation_increases_on_every_record(self):
        initialize(str(self.root), 3)
        one = evaluate_and_record(str(self.root), "RUNNING")
        two = evaluate_and_record(str(self.root), "HEALTHY")
        self.assertEqual((one["generation"], two["generation"]), (1, 2))

    def test_bool_budget_rejected(self):
        with self.assertRaises(RestartLedgerError):
            initialize(str(self.root), True)

    def test_zero_budget_rejected(self):
        with self.assertRaises(RestartLedgerError):
            initialize(str(self.root), 0)

    def test_invalid_runtime_status_rejected_without_commit(self):
        initialize(str(self.root), 3)
        before = read_ledger(str(self.root))
        with self.assertRaises(RestartLedgerError):
            evaluate_and_record(str(self.root), "UNKNOWN")
        self.assertEqual(read_ledger(str(self.root)), before)

    def test_initialize_existing_ledger_fails_closed(self):
        initialize(str(self.root), 3)
        with self.assertRaises(RestartLedgerError):
            initialize(str(self.root), 3)

    def test_corrupt_checkpoint_fails_closed(self):
        initialize(str(self.root), 3)
        (self.root / "checkpoint.json").write_text("garbage\n")
        with self.assertRaises(RestartLedgerError):
            read_ledger(str(self.root))

    def test_wrong_payload_shape_fails_closed(self):
        from kk_f.checkpoint import write_checkpoint
        write_checkpoint(str(self.root), 0, "READY", {"unexpected": True})
        with self.assertRaises(RestartLedgerError):
            read_ledger(str(self.root))

    def test_invalid_last_decision_fails_closed(self):
        from kk_f.checkpoint import write_checkpoint
        payload = {"ledger_version": "0.1", "attempts": 0, "max_attempts": 3, "last_decision": "MAGIC"}
        write_checkpoint(str(self.root), 0, "READY", payload)
        with self.assertRaises(RestartLedgerError):
            read_ledger(str(self.root))

    def test_attempts_above_max_in_payload_rejected(self):
        from kk_f.checkpoint import write_checkpoint
        payload = {"ledger_version": "0.1", "attempts": 4, "max_attempts": 3, "last_decision": "NO_ACTION"}
        write_checkpoint(str(self.root), 0, "READY", payload)
        with self.assertRaises(RestartLedgerError):
            read_ledger(str(self.root))

    def test_atomic_replace_failure_preserves_prior_ledger(self):
        initialize(str(self.root), 3)
        before = read_ledger(str(self.root))
        with mock.patch("kk_f.checkpoint.os.replace", side_effect=OSError("simulated replace failure")):
            with self.assertRaises(RestartLedgerError):
                evaluate_and_record(str(self.root), "FAILED")
        self.assertEqual(read_ledger(str(self.root)), before)

    def test_missing_ledger_fails_closed(self):
        with self.assertRaises(RestartLedgerError):
            read_ledger(str(self.root))


if __name__ == "__main__":
    unittest.main()
