import copy
import unittest

from kk_k.constitution import load_constitution
from kk_k.goal_anchor import GoalAnchorError, assert_system_alignment, assert_runtime_scope_alignment, load_goal_anchor, validate_goal_anchor, EXPECTED_ACTIONS, EXPECTED_EXTERNAL_TOOLS
from kk_k.identity import load_identity
from kk_k.action_registry import ALLOWED_ACTIONS
from kk_k.external_tools import load_external_catalog


class KGoalAnchorTests(unittest.TestCase):
    def test_live_goal_anchor_aligns_with_constitution_and_identity(self):
        anchor=load_goal_anchor()
        assert_system_alignment(anchor,load_constitution('/root/K/K/K00_CONSTITUTION.json'),load_identity('/root/K/K/K_IDENTITY.json'))

    def test_model_cannot_become_k_identity(self):
        anchor=load_goal_anchor()
        identity=load_identity('/root/K/K/K_IDENTITY.json')
        bad=dict(identity); bad['model_is_identity']=True
        with self.assertRaisesRegex(GoalAnchorError,'identity drift'):
            assert_system_alignment(anchor,load_constitution('/root/K/K/K00_CONSTITUTION.json'),bad)

    def test_f_cognitive_veto_cannot_return(self):
        anchor=load_goal_anchor(); constitution=load_constitution('/root/K/K/K00_CONSTITUTION.json')
        bad=dict(constitution); bad['k_f_boundary']='F_FINAL_VETO'
        with self.assertRaisesRegex(GoalAnchorError,'constitution drift'):
            assert_system_alignment(anchor,bad,load_identity('/root/K/K/K_IDENTITY.json'))

    def test_history_rewrite_cannot_be_enabled(self):
        anchor=load_goal_anchor(); constitution=load_constitution('/root/K/K/K00_CONSTITUTION.json')
        bad=dict(constitution); bad['historical_record_rewrite_allowed']=True
        with self.assertRaisesRegex(GoalAnchorError,'constitution drift'):
            assert_system_alignment(anchor,bad,load_identity('/root/K/K/K_IDENTITY.json'))

    def test_success_criteria_cannot_move_after_result(self):
        anchor=load_goal_anchor(); constitution=load_constitution('/root/K/K/K00_CONSTITUTION.json')
        bad=dict(constitution); bad['success_criteria_mutable_after_result']=True
        with self.assertRaisesRegex(GoalAnchorError,'constitution drift'):
            assert_system_alignment(anchor,bad,load_identity('/root/K/K/K_IDENTITY.json'))

    def test_goal_anchor_exact_fields_fail_closed(self):
        state=copy.deepcopy(load_goal_anchor().state); state['new_rule']='silent drift'
        with self.assertRaises(GoalAnchorError): validate_goal_anchor(state)



    def test_live_runtime_scope_is_exact_original_design(self):
        anchor=load_goal_anchor()
        catalog=load_external_catalog()
        enabled={name for name,spec in catalog.items() if spec.enabled}
        self.assertEqual(enabled,EXPECTED_EXTERNAL_TOOLS)
        self.assertEqual(ALLOWED_ACTIONS,EXPECTED_ACTIONS)
        assert_runtime_scope_alignment(anchor,enabled,ALLOWED_ACTIONS)

    def test_fourth_cognitive_tool_is_goal_drift(self):
        anchor=load_goal_anchor()
        with self.assertRaisesRegex(GoalAnchorError,'external tool scope drift'):
            assert_runtime_scope_alignment(anchor,set(EXPECTED_EXTERNAL_TOOLS)|{'files.write'},ALLOWED_ACTIONS)

    def test_sixth_action_is_goal_drift(self):
        anchor=load_goal_anchor()
        with self.assertRaisesRegex(GoalAnchorError,'action scope drift'):
            assert_runtime_scope_alignment(anchor,EXPECTED_EXTERNAL_TOOLS,set(ALLOWED_ACTIONS)|{'A06_GENERIC_PROCESS'})

    def test_missing_no_action_is_goal_drift(self):
        anchor=load_goal_anchor()
        with self.assertRaisesRegex(GoalAnchorError,'action scope drift'):
            assert_runtime_scope_alignment(anchor,EXPECTED_EXTERNAL_TOOLS,set(ALLOWED_ACTIONS)-{'A05_NO_ACTION'})

if __name__=='__main__': unittest.main()
