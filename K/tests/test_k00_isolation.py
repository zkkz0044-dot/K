import unittest
from pathlib import Path

from kk_k.audit import append_jsonl
from kk_k.constitution import ConstitutionError, load_constitution
from kk_k.governance import GovernanceError, load_policy
from kk_k.isolation import IsolationError, PROJECT_ROOT, project_path
from kk_k.memory import load_goal, verify_event_log, write_goal_atomic
from kk_k.test_support import project_tempdir


class IsolationTests(unittest.TestCase):
    def test_project_root_and_nested_paths_allowed(self):
        self.assertEqual(project_path('/root/K/K'), PROJECT_ROOT)
        self.assertEqual(project_path('state/example.json'), PROJECT_ROOT / 'state/example.json')

    def test_parent_escape_rejected(self):
        with self.assertRaises(IsolationError):
            project_path('../outside-sentinel')

    def test_absolute_outside_path_rejected(self):
        with self.assertRaises(IsolationError):
            project_path('/root/outside-sentinel')

    def test_project_file_apis_reject_outside_paths(self):
        bad = '/root/outside-sentinel'
        with self.assertRaises(ConstitutionError):
            load_constitution(bad)
        with self.assertRaises(GovernanceError):
            load_policy(bad)
        with self.assertRaises(IsolationError):
            load_goal(bad)
        with self.assertRaises(IsolationError):
            verify_event_log(bad)
        with self.assertRaises(IsolationError):
            append_jsonl(bad, {'x': 1})

    def test_project_file_apis_work_inside_root(self):
        with project_tempdir() as td:
            root = Path(td)
            goal = root / 'goal.json'
            value = {'schema':'K02.GOAL.1','goal_id':'iso','text':'inside only','status':'ACTIVE'}
            write_goal_atomic(str(goal), value)
            self.assertEqual(load_goal(str(goal)), value)

    def test_authoritative_constitution_carries_isolation_invariants(self):
        value = load_constitution('/root/K/K/K00_CONSTITUTION.json')
        self.assertEqual(value['project_root'], '/root/K/K')
        self.assertEqual(value['filesystem_scope'], 'PROJECT_ROOT_ONLY')
        self.assertFalse(value['cross_project_access'])
        self.assertFalse(value['webroot_staging'])
        self.assertFalse(value['temporary_http_transfer'])
