import json
import tempfile
import unittest
from pathlib import Path

from kk_k.test_support import project_tempdir
from kk_k.governance import GovernanceError, govern, load_policy, validate_policy


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy("/root/K/K/K06_POLICY.json")

    def test_allow_safe_action(self):
        d = govern("A02_READ_F_STATUS", self.policy, [])
        self.assertEqual((d.outcome,d.action_id),("ALLOW","A02_READ_F_STATUS"))

    def test_human_required_cannot_allow(self):
        d = govern("A03_RUN_F_SMOKE_TEST", self.policy, [])
        self.assertEqual(d.outcome,"REQUIRE_HUMAN")

    def test_run_budget_stops_to_no_action(self):
        d = govern("A02_READ_F_STATUS", self.policy, ["A01_READ_PROJECT_STATE"]*8)
        self.assertEqual((d.outcome,d.action_id),("STOP","A05_NO_ACTION"))

    def test_consecutive_budget_stops(self):
        d = govern("A02_READ_F_STATUS", self.policy, ["A02_READ_F_STATUS","A02_READ_F_STATUS"])
        self.assertEqual(d.action_id,"A05_NO_ACTION")

    def test_unknown_requested_action_rejected(self):
        with self.assertRaises(GovernanceError): govern("RUN_SHELL",self.policy,[])

    def test_no_action_uses_governance(self):
        d=govern("A05_NO_ACTION",self.policy,[])
        self.assertEqual(d.outcome,"ALLOW")

    def test_policy_without_no_action_rejected(self):
        p=dict(self.policy); p["allowed_actions"]=["A02_READ_F_STATUS"]
        with self.assertRaises(GovernanceError): validate_policy(p)

    def test_policy_extra_field_rejected(self):
        raw=json.loads(Path("/root/K/K/K06_POLICY.json").read_text()); raw["extra"]=1
        td=project_tempdir(); path=Path(td.name)/"p.json"; path.write_text(json.dumps(raw))
        try:
            with self.assertRaises(GovernanceError): load_policy(str(path))
        finally: td.cleanup()

    def test_policy_duplicate_key_rejected(self):
        raw='{"schema":"K06.POLICY.1","schema":"K06.POLICY.1"}'
        td=project_tempdir(); path=Path(td.name)/"p.json"; path.write_text(raw)
        try:
            with self.assertRaises(GovernanceError): load_policy(str(path))
        finally: td.cleanup()

    def test_bad_budget_bool_rejected(self):
        p=dict(self.policy); p["max_actions_per_run"]=True
        with self.assertRaises(GovernanceError): validate_policy(p)

    def test_disallowed_action_denied(self):
        p=dict(self.policy); p["allowed_actions"]=["A02_READ_F_STATUS","A05_NO_ACTION"]; p["human_required_actions"]=[]
        d=govern("A01_READ_PROJECT_STATE",p,[])
        self.assertEqual((d.outcome,d.action_id),("DENY","A05_NO_ACTION"))

    def test_invalid_history_rejected(self):
        with self.assertRaises(GovernanceError): govern("A02_READ_F_STATUS",self.policy,["RUN_SHELL"])

if __name__ == "__main__":
    unittest.main()
