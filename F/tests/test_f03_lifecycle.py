import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.contracts import RUNTIME_STATUSES
from kk_f.lifecycle import LEGAL_TRANSITIONS, LifecycleError, allowed_targets, evaluate_transition


class F03LifecycleTests(unittest.TestCase):
    def test_table_covers_exact_f01_runtime_statuses(self):
        self.assertEqual(frozenset(LEGAL_TRANSITIONS), RUNTIME_STATUSES)

    def test_all_declared_transitions_are_accepted(self):
        for source, targets in LEGAL_TRANSITIONS.items():
            for target in targets:
                with self.subTest(source=source, target=target):
                    result = evaluate_transition(source, target)
                    self.assertEqual(result, {"from": source, "to": target, "changed": True})

    def test_all_undeclared_nonself_transitions_are_rejected(self):
        for source in RUNTIME_STATUSES:
            for target in RUNTIME_STATUSES:
                if source != target and target not in LEGAL_TRANSITIONS[source]:
                    with self.subTest(source=source, target=target):
                        with self.assertRaises(LifecycleError):
                            evaluate_transition(source, target)

    def test_self_requests_are_idempotent(self):
        for state in RUNTIME_STATUSES:
            with self.subTest(state=state):
                self.assertEqual(
                    evaluate_transition(state, state),
                    {"from": state, "to": state, "changed": False},
                )

    def test_stopped_is_terminal_except_idempotent_request(self):
        self.assertEqual(allowed_targets("STOPPED"), ())
        for target in RUNTIME_STATUSES - {"STOPPED"}:
            with self.assertRaises(LifecycleError):
                evaluate_transition("STOPPED", target)

    def test_failed_can_only_progress_to_stopped(self):
        self.assertEqual(allowed_targets("FAILED"), ("STOPPED",))
        for target in RUNTIME_STATUSES - {"FAILED", "STOPPED"}:
            with self.assertRaises(LifecycleError):
                evaluate_transition("FAILED", target)

    def test_ready_is_not_healthy(self):
        with self.assertRaises(LifecycleError):
            evaluate_transition("READY", "HEALTHY")

    def test_running_is_not_healthy(self):
        self.assertTrue(evaluate_transition("RUNNING", "HEALTHY")["changed"])

    def test_blocked_can_reenter_running_for_recovery(self):
        self.assertTrue(evaluate_transition("BLOCKED", "RUNNING")["changed"])

    def test_unknown_current_rejected(self):
        with self.assertRaises(LifecycleError):
            evaluate_transition("UNKNOWN", "RUNNING")

    def test_unknown_target_rejected(self):
        with self.assertRaises(LifecycleError):
            evaluate_transition("READY", "UNKNOWN")

    def test_type_confusion_rejected(self):
        bad_values = [None, True, 1, 1.0, [], {}, ()]
        for value in bad_values:
            with self.subTest(value=value):
                with self.assertRaises(LifecycleError):
                    evaluate_transition(value, "RUNNING")
                with self.assertRaises(LifecycleError):
                    evaluate_transition("READY", value)

    def test_allowed_targets_are_sorted_and_immutable(self):
        targets = allowed_targets("RUNNING")
        self.assertIsInstance(targets, tuple)
        self.assertEqual(targets, tuple(sorted(targets)))


if __name__ == "__main__":
    unittest.main()
