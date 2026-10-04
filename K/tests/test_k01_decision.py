import unittest

from kk_k.decision import DecisionError, parse_decision


class DecisionTests(unittest.TestCase):
    def test_accepts_exact_valid_object(self):
        d = parse_decision('{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}')
        self.assertEqual(d.action_id, "A05_NO_ACTION")

    def test_rejects_extra_field(self):
        with self.assertRaises(DecisionError):
            parse_decision('{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION","params":{}}')

    def test_rejects_duplicate_key(self):
        with self.assertRaises(DecisionError):
            parse_decision('{"schema":"K01.DECISION.1","schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}')

    def test_rejects_unknown_action(self):
        with self.assertRaises(DecisionError):
            parse_decision('{"schema":"K01.DECISION.1","action_id":"RUN_SHELL"}')

    def test_rejects_trailing_object(self):
        with self.assertRaises(DecisionError):
            parse_decision('{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"} {}')

    def test_rejects_wrong_schema(self):
        with self.assertRaises(DecisionError):
            parse_decision('{"schema":"K01.DECISION.0","action_id":"A05_NO_ACTION"}')

    def test_rejects_non_string(self):
        with self.assertRaises(DecisionError):
            parse_decision({"schema": "K01.DECISION.1", "action_id": "A05_NO_ACTION"})

    def test_rejects_oversize(self):
        raw = '{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}' + (" " * 2000)
        with self.assertRaises(DecisionError):
            parse_decision(raw)


if __name__ == "__main__":
    unittest.main()
