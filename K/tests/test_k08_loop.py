import tempfile
import unittest
from pathlib import Path

from kk_k.test_support import project_tempdir
from kk_k.loop import LoopError, run_bounded_loop
from kk_k.governance import load_policy


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=project_tempdir(); self.log=str(Path(self.tmp.name)/"loop.jsonl")
        self.policy=load_policy("/root/K/K/K06_POLICY.json")
    def tearDown(self): self.tmp.cleanup()
    def executor(self, verdict="PASS"):
        return lambda action_id:{"action_id":action_id,"mechanical_verdict":verdict}

    def test_no_action_traverses_executor_then_stops(self):
        seen=[]
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"A05_NO_ACTION",executor=lambda a: seen.append(a) or {"action_id":a,"mechanical_verdict":"PASS"},log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"NO_ACTION"); self.assertEqual(seen,["A05_NO_ACTION"])

    def test_fail_stops_without_retry(self):
        calls=[]
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"A02_READ_F_STATUS",executor=lambda a:calls.append(a) or {"action_id":a,"mechanical_verdict":"FAIL"},log_path=self.log,max_cycles=8)
        self.assertEqual((r["status"],len(calls)),("FAIL",1))

    def test_veto_stops(self):
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"A02_READ_F_STATUS",executor=self.executor("VETO"),log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"VETO")

    def test_human_required_stops_before_executor(self):
        calls=[]
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"A03_RUN_F_SMOKE_TEST",executor=lambda a:calls.append(a),log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"REQUIRE_HUMAN"); self.assertEqual(calls,[])

    def test_policy_budget_stops_before_second_executor(self):
        p=dict(self.policy); p["human_required_actions"]=[]; p["max_actions_per_run"]=1
        calls=[]
        r=run_bounded_loop(policy=p,proposer=lambda i:"A02_READ_F_STATUS",executor=lambda a:calls.append(a) or {"action_id":a,"mechanical_verdict":"PASS"},log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"STOP"); self.assertEqual(len(calls),1)

    def test_proposer_error_no_executor(self):
        calls=[]
        def bad(_): raise RuntimeError("x")
        r=run_bounded_loop(policy=self.policy,proposer=bad,executor=lambda a:calls.append(a),log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"PROPOSER_ERROR"); self.assertEqual(calls,[])

    def test_executor_error_no_retry(self):
        calls=[]
        def bad(a): calls.append(a); raise RuntimeError("x")
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"A02_READ_F_STATUS",executor=bad,log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"EXECUTOR_ERROR"); self.assertEqual(len(calls),1)

    def test_malformed_result_is_executor_error(self):
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"A02_READ_F_STATUS",executor=lambda a:{"action_id":a,"mechanical_verdict":"PASS","extra":1},log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"EXECUTOR_ERROR")

    def test_hard_max_cycles(self):
        p=dict(self.policy); p["human_required_actions"]=[]; p["max_actions_per_run"]=32; p["max_same_action_consecutive"]=8
        r=run_bounded_loop(policy=p,proposer=lambda i:"A01_READ_PROJECT_STATE" if i%2 else "A02_READ_F_STATUS",executor=self.executor(),log_path=self.log,max_cycles=32)
        self.assertEqual((r["status"],r["cycles"],r["proposer_calls"],r["executor_calls"]),("MAX_CYCLES",32,32,32))

    def test_invalid_max_cycles_rejected(self):
        with self.assertRaises(LoopError):
            run_bounded_loop(policy=self.policy,proposer=lambda _:"A05_NO_ACTION",executor=self.executor(),log_path=self.log,max_cycles=33)

    def test_unknown_action_governance_rejects(self):
        r=run_bounded_loop(policy=self.policy,proposer=lambda _:"RUN_SHELL",executor=self.executor(),log_path=self.log,max_cycles=8)
        self.assertEqual(r["status"],"GOVERNANCE_REJECTED")

    def test_log_records_each_attempted_cycle(self):
        p=dict(self.policy); p["human_required_actions"]=[]; p["max_actions_per_run"]=2
        run_bounded_loop(policy=p,proposer=lambda _:"A02_READ_F_STATUS",executor=self.executor(),log_path=self.log,max_cycles=8)
        lines=Path(self.log).read_text().splitlines()
        self.assertEqual(len(lines),3)

if __name__ == "__main__":
    unittest.main()
