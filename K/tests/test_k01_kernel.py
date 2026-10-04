import json
import tempfile
import unittest
from pathlib import Path

from kk_k.test_support import project_tempdir
from kk_k.kernel import run_once


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = project_tempdir()
        self.root = Path(self.tmp.name)
        self.constitution = self.root / "constitution.md"
        self.goal = self.root / "goal.json"
        self.world = self.root / "world.json"
        self.dlog = self.root / "decision.jsonl"
        self.elog = self.root / "execution.jsonl"
        self.constitution.write_text(Path("/root/K/K/K00_CONSTITUTION.json").read_text(encoding="utf-8"), encoding="utf-8")
        self.goal.write_text('{"goal":"inspect only"}', encoding="utf-8")
        self.world.write_text('{"f":"ACCEPTED"}', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_kernel(self, llm, gateway):
        return run_once(
            constitution_path=str(self.constitution), goal_path=str(self.goal),
            world_state_path=str(self.world), decision_log_path=str(self.dlog),
            execution_log_path=str(self.elog), llm_call=llm, f_submit=gateway,
        )

    def test_valid_no_action_one_call_one_submit(self):
        counts = {"llm": 0, "f": 0}
        def llm(_prompt):
            counts["llm"] += 1
            return '{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}'
        def gateway(action_id):
            counts["f"] += 1
            self.assertEqual(action_id, "A05_NO_ACTION")
            return {
                "schema": "K01.F_RECEIPT.1", "action_id": action_id,
                "outcome": "EXECUTED",
                "evidence": {"kind": "NO_ACTION", "process_started": False},
            }
        result = self.run_kernel(llm, gateway)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(counts, {"llm": 1, "f": 1})

    def test_invalid_llm_output_never_calls_f(self):
        called = {"f": 0}
        def gateway(_action_id):
            called["f"] += 1
            raise AssertionError("must not be called")
        result = self.run_kernel(lambda _: '{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION","params":{}}', gateway)
        self.assertEqual(result["status"], "DECISION_REJECTED")
        self.assertEqual(called["f"], 0)

    def test_gateway_error_has_no_retry(self):
        counts = {"f": 0}
        def gateway(_action_id):
            counts["f"] += 1
            raise RuntimeError("boom")
        result = self.run_kernel(
            lambda _: '{"schema":"K01.DECISION.1","action_id":"A02_READ_F_STATUS"}',
            gateway,
        )
        self.assertEqual(result["status"], "GATEWAY_ERROR")
        self.assertEqual(counts["f"], 1)

    def test_bad_receipt_rejected(self):
        def gateway(action_id):
            return {
                "schema": "K01.F_RECEIPT.1", "action_id": action_id,
                "outcome": "EXECUTED",
                "evidence": {"kind": "NO_ACTION", "process_started": False, "extra": 1},
            }
        result = self.run_kernel(
            lambda _: '{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}',
            gateway,
        )
        self.assertEqual(result["status"], "RECEIPT_REJECTED")


if __name__ == "__main__":
    unittest.main()
