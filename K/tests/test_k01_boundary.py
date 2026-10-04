import unittest

from kk_k.action_registry import ALLOWED_ACTIONS, ActionRegistryError, get_action_spec
from kk_k.boundary import BoundaryError, submit_action


class BoundaryTests(unittest.TestCase):
    def test_all_five_actions_use_registry_and_transport(self):
        seen = []
        def transport(action_id):
            seen.append(action_id)
            return {"action_id": action_id}
        for action_id in sorted(ALLOWED_ACTIONS):
            out = submit_action(action_id, transport)
            self.assertEqual(out["action_id"], action_id)
        self.assertEqual(set(seen), set(ALLOWED_ACTIONS))

    def test_unknown_action_rejected_before_transport(self):
        called = []
        with self.assertRaises(BoundaryError):
            submit_action("RUN_SHELL", lambda x: called.append(x))
        self.assertEqual(called, [])

    def test_transport_receives_only_action_id_string(self):
        observed = []
        submit_action("A05_NO_ACTION", lambda x: observed.append(x) or {})
        self.assertEqual(observed, ["A05_NO_ACTION"])

    def test_registry_exact_count(self):
        self.assertEqual(len(ALLOWED_ACTIONS), 5)

    def test_registry_has_fixed_verifier_per_action(self):
        for action_id in ALLOWED_ACTIONS:
            spec = get_action_spec(action_id)
            self.assertTrue(spec.verifier_id.startswith("VERIFY_A"))
            self.assertTrue(spec.enabled)

    def test_registry_rejects_non_string(self):
        with self.assertRaises(ActionRegistryError):
            get_action_spec({"action_id": "A05_NO_ACTION"})

if __name__ == "__main__":
    unittest.main()
