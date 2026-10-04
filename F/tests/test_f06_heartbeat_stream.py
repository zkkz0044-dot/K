import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.heartbeat_stream import HeartbeatStreamError, advance

PREV = {"version": "0.1", "sequence": 7, "observed_at": "2026-09-04T02:40:00Z"}
CURR = {"version": "0.1", "sequence": 8, "observed_at": "2026-09-04T02:40:01Z"}


class F06HeartbeatStreamTests(unittest.TestCase):
    def test_first_heartbeat_accepted(self):
        result = advance(None, CURR)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["sequence"], 8)

    def test_strict_advance_accepted(self):
        self.assertEqual(advance(PREV, CURR)["sequence"], 8)

    def test_sequence_replay_rejected(self):
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, dict(CURR, sequence=7))

    def test_sequence_regression_rejected(self):
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, dict(CURR, sequence=6))

    def test_equal_timestamp_rejected(self):
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, dict(CURR, observed_at=PREV["observed_at"]))

    def test_timestamp_regression_rejected(self):
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, dict(CURR, observed_at="2026-09-04T02:39:59Z"))

    def test_sequence_jump_allowed(self):
        result = advance(PREV, dict(CURR, sequence=100))
        self.assertEqual(result["sequence"], 100)

    def test_timezone_equivalent_nonadvance_rejected(self):
        current = dict(CURR, observed_at="2026-09-04T10:40:00+08:00")
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, current)

    def test_timezone_offset_strict_advance_accepted(self):
        current = dict(CURR, observed_at="2026-09-04T10:40:01+08:00")
        self.assertTrue(advance(PREV, current)["accepted"])

    def test_fractional_timestamp_advance_accepted(self):
        current = dict(CURR, observed_at="2026-09-04T02:40:00.000001Z")
        self.assertTrue(advance(PREV, current)["accepted"])

    def test_invalid_previous_wrapped(self):
        with self.assertRaises(HeartbeatStreamError):
            advance({"bad": True}, CURR)

    def test_invalid_current_wrapped(self):
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, {"bad": True})

    def test_bool_sequence_rejected(self):
        with self.assertRaises(HeartbeatStreamError):
            advance(PREV, dict(CURR, sequence=True))

    def test_future_semantics_not_inferred(self):
        future = dict(CURR, observed_at="2099-01-01T00:00:00Z")
        self.assertTrue(advance(PREV, future)["accepted"])


if __name__ == "__main__":
    unittest.main()
