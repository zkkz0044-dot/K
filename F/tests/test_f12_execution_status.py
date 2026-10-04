import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.execution_status import ExecutionStatusError, classify_execution


class F12ExecutionStatusTests(unittest.TestCase):
    def test_running_when_no_exit(self):
        self.assertEqual(classify_execution(exit_code=None, timed_out=False), "RUNNING")

    def test_clean_exit_is_stopped_not_healthy(self):
        self.assertEqual(classify_execution(exit_code=0, timed_out=False), "STOPPED")

    def test_nonzero_exit_failed(self):
        self.assertEqual(classify_execution(exit_code=7, timed_out=False), "FAILED")

    def test_negative_signal_exit_failed(self):
        self.assertEqual(classify_execution(exit_code=-9, timed_out=False), "FAILED")

    def test_timeout_failed(self):
        self.assertEqual(classify_execution(exit_code=-9, timed_out=True), "FAILED")

    def test_timed_out_requires_reaped_exit_code(self):
        with self.assertRaises(ExecutionStatusError):
            classify_execution(exit_code=None, timed_out=True)

    def test_bool_exit_code_rejected(self):
        with self.assertRaises(ExecutionStatusError):
            classify_execution(exit_code=True, timed_out=False)

    def test_string_exit_code_rejected(self):
        with self.assertRaises(ExecutionStatusError):
            classify_execution(exit_code="0", timed_out=False)

    def test_timed_out_type_confusion_rejected(self):
        with self.assertRaises(ExecutionStatusError):
            classify_execution(exit_code=0, timed_out=1)

    def test_exit_zero_never_claims_healthy(self):
        self.assertNotEqual(classify_execution(exit_code=0, timed_out=False), "HEALTHY")


if __name__ == "__main__":
    unittest.main()
