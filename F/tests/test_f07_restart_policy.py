import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.contracts import RUNTIME_STATUSES
from kk_f.restart_policy import DECISIONS, RestartPolicyError, decide


class F07RestartPolicyTests(unittest.TestCase):
    def test_failed_below_budget_replaces(self):
        self.assertEqual(decide("FAILED", 0, 3)["decision"], "REPLACE_INSTANCE")

    def test_failed_last_available_attempt_replaces(self):
        self.assertEqual(decide("FAILED", 2, 3)["decision"], "REPLACE_INSTANCE")

    def test_failed_at_budget_holds(self):
        self.assertEqual(decide("FAILED", 3, 3)["decision"], "HOLD_FAILED")

    def test_all_nonfailed_statuses_no_action(self):
        for status in RUNTIME_STATUSES - {"FAILED"}:
            with self.subTest(status=status):
                self.assertEqual(decide(status, 0, 3)["decision"], "NO_ACTION")

    def test_unknown_status_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide("UNKNOWN", 0, 3)

    def test_status_type_confusion_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide(1, 0, 3)

    def test_bool_attempts_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide("FAILED", True, 3)

    def test_negative_attempts_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide("FAILED", -1, 3)

    def test_zero_budget_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide("FAILED", 0, 0)

    def test_bool_budget_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide("FAILED", 0, True)

    def test_attempts_above_budget_rejected(self):
        with self.assertRaises(RestartPolicyError):
            decide("FAILED", 4, 3)

    def test_decision_vocabulary_exact(self):
        self.assertEqual(DECISIONS, frozenset({"NO_ACTION", "REPLACE_INSTANCE", "HOLD_FAILED"}))

    def test_return_is_deterministic(self):
        expected = {"status": "FAILED", "attempts": 1, "max_attempts": 3, "decision": "REPLACE_INSTANCE"}
        self.assertEqual(decide("FAILED", 1, 3), expected)


if __name__ == "__main__":
    unittest.main()
