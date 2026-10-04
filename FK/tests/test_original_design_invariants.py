from __future__ import annotations
import json, sys, unittest
from pathlib import Path
for path in ("/root/K/K/src","/root/K/F/src"):
    if path not in sys.path: sys.path.insert(0,path)
from kk_k.external_tools import external_catalog_status
from kk_k.goal_anchor import load_goal_anchor
from kk_k.constitution import load_constitution
from kk_k.identity import load_identity
from kk_f.fk_tool_gateway import ENABLED_TOOLS

EXPECTED_TOOLS=frozenset({"files.read","browser.search","remote.vps.health"})
EXPECTED_ACTIONS=["A01_READ_PROJECT_STATE","A02_READ_F_STATUS","A03_RUN_F_SMOKE_TEST","A04_WRITE_K_DECISION_LOG","A05_NO_ACTION"]

class OriginalDesignInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=json.loads(Path("/root/K/K/PROJECT_STATE.json").read_text())
        cls.anchor=load_goal_anchor().state
        cls.constitution=load_constitution("/root/K/K/K00_CONSTITUTION.json")
        cls.identity=load_identity("/root/K/K/K_IDENTITY.json")

    def test_k_is_persistent_identity_not_model(self):
        self.assertEqual(self.anchor["identity_goal"],"ONE_PERSISTENT_PERSONAL_AGENT_K")
        self.assertEqual(self.anchor["model_relation"],"REPLACEABLE_COGNITIVE_ENGINE_NOT_IDENTITY")
        self.assertFalse(self.identity["model_is_identity"])

    def test_k_f_original_boundary_is_preserved(self):
        self.assertEqual(self.constitution["k_f_boundary"],"K_FINAL_DECISION_F_EXECUTION_GUARD")
        self.assertEqual(self.state["k_f_boundary"],"K_FINAL_DECISION_F_EXECUTION_GUARD")
        self.assertIn("NO_COGNITIVE_VETO",self.anchor["f_role"])

    def test_cognitive_external_surface_remains_exact_three_readonly_evidence_tools(self):
        catalog={x["name"]:x for x in external_catalog_status()}
        enabled=frozenset(name for name,item in catalog.items() if item["enabled"])
        self.assertEqual(enabled,EXPECTED_TOOLS)
        self.assertEqual(ENABLED_TOOLS,EXPECTED_TOOLS)
        self.assertEqual(frozenset(self.state["external_tools_enabled"]),EXPECTED_TOOLS)
        self.assertEqual(frozenset(self.state["k_cognition_external_tools"]["enabled"]),EXPECTED_TOOLS)
        self.assertEqual(self.state["external_tool_scope"],"ACCEPTED_EXACT_THREE_READONLY")
        self.assertFalse(catalog["files.write"]["enabled"])

    def test_action_surface_remains_fixed_a01_to_a05(self):
        self.assertEqual(self.state["fk_enabled_actions"],EXPECTED_ACTIONS)
        self.assertEqual(self.state["initial_action_count"],5)
        self.assertFalse(self.state["dynamic_process_spec_enabled"])
        self.assertFalse(self.state["free_form_params_enabled"])
        self.assertFalse(self.constitution["free_form_execution_authority"])

    def test_world_observation_remains_evidence_only(self):
        world=self.state["world_observation_cycle"]
        self.assertEqual(world["authority"],"EVIDENCE_ONLY")
        self.assertEqual(world["mode"],"OBSERVE_ONLY")
        self.assertEqual(world["promotion_policy"],"NO_AUTO_TRUTH_NO_EXECUTION_AUTHORITY")
        self.assertEqual(self.anchor["world_rule"],"OBSERVATION_IS_NOT_TRUTH_UNTIL_EVIDENCE_SUPPORTS_BELIEF")

    def test_history_and_chat_cannot_become_execution_authority(self):
        self.assertFalse(self.constitution["historical_record_rewrite_allowed"])
        self.assertEqual(self.state["human_interface"],"PASS_COGNITIVE_ONLY_NO_EXECUTION")
        self.assertEqual(self.anchor["execution_rule"],"CHAT_IS_NOT_EXECUTION_AUTHORITY_EXPLICIT_CONTRACT_REQUIRED")

if __name__=="__main__": unittest.main()
