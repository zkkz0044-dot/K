import copy
import json
import unittest
from pathlib import Path

from kk_k.personality import PersonalityError, load_personality_core, personality_sha256, prompt_view, validate_personality
from kk_k.test_support import project_tempdir


class PersonalityCoreTests(unittest.TestCase):
    def setUp(self):
        self.live = load_personality_core()

    def test_live_core_is_valid_and_model_is_not_personality(self):
        self.assertEqual(self.live.state["identity_id"], "KK-K")
        self.assertIs(self.live.state["model_is_personality"], False)
        self.assertEqual(self.live.state["change_policy"], "SLOW_APPEND_ONLY_EVIDENCE_LINKED")

    def test_hash_is_deterministic(self):
        self.assertEqual(personality_sha256(self.live.state), self.live.sha256)
        clone = json.loads(json.dumps(self.live.state, ensure_ascii=False))
        self.assertEqual(personality_sha256(clone), self.live.sha256)

    def test_unknown_or_missing_trait_fails_closed(self):
        bad = copy.deepcopy(self.live.state)
        bad["traits"]["invented"] = bad["traits"]["curiosity"]
        with self.assertRaises(PersonalityError): validate_personality(bad)
        bad = copy.deepcopy(self.live.state)
        del bad["traits"]["warmth"]
        with self.assertRaises(PersonalityError): validate_personality(bad)

    def test_model_identity_escalation_fails_closed(self):
        bad = copy.deepcopy(self.live.state)
        bad["model_is_personality"] = True
        with self.assertRaises(PersonalityError): validate_personality(bad)

    def test_prompt_view_marks_self_state_not_fact_authority(self):
        view = prompt_view(self.live)
        self.assertEqual(view["authority"], "SELF_STATE_NOT_FACT_AUTHORITY")
        self.assertEqual(view["revision_count"], 0)
        self.assertEqual(set(view["traits"]), set(self.live.state["traits"]))

    def test_root_authority_loader_rejects_group_writable_file(self):
        with project_tempdir() as td:
            p = Path(td) / "personality.json"
            p.write_text(json.dumps(self.live.state, ensure_ascii=False), encoding="utf-8")
            p.chmod(0o666)
            with self.assertRaises(PersonalityError): load_personality_core(str(p))


if __name__ == "__main__":
    unittest.main()
