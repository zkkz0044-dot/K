import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.heartbeat import HeartbeatError, evaluate_freshness, validate_heartbeat

BASE = {
    "version": "0.1",
    "sequence": 7,
    "observed_at": "2026-09-04T02:40:00Z",
}
NOW = "2026-09-04T02:40:30Z"


class F05HeartbeatTests(unittest.TestCase):
    def test_valid_heartbeat(self):
        self.assertEqual(validate_heartbeat(dict(BASE)), BASE)

    def test_healthy_boundary(self):
        result = evaluate_freshness(BASE, now=NOW, healthy_within_seconds=30, degraded_within_seconds=60)
        self.assertEqual(result["status"], "HEALTHY")
        self.assertEqual(result["age_seconds"], 30.0)

    def test_degraded_range(self):
        hb = dict(BASE, observed_at="2026-09-04T02:39:31Z")
        self.assertEqual(evaluate_freshness(hb, now=NOW, healthy_within_seconds=30, degraded_within_seconds=60)["status"], "DEGRADED")

    def test_degraded_boundary(self):
        hb = dict(BASE, observed_at="2026-09-04T02:39:30Z")
        self.assertEqual(evaluate_freshness(hb, now=NOW, healthy_within_seconds=30, degraded_within_seconds=60)["status"], "DEGRADED")

    def test_failed_when_stale(self):
        hb = dict(BASE, observed_at="2026-09-04T02:39:29Z")
        self.assertEqual(evaluate_freshness(hb, now=NOW, healthy_within_seconds=30, degraded_within_seconds=60)["status"], "FAILED")

    def test_future_heartbeat_rejected(self):
        hb = dict(BASE, observed_at="2026-09-04T02:40:31Z")
        with self.assertRaises(HeartbeatError):
            evaluate_freshness(hb, now=NOW, healthy_within_seconds=30, degraded_within_seconds=60)

    def test_unknown_field_rejected(self):
        hb = dict(BASE, extra=True)
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(hb)

    def test_missing_field_rejected(self):
        hb = dict(BASE)
        del hb["sequence"]
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(hb)

    def test_bool_sequence_rejected(self):
        hb = dict(BASE, sequence=True)
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(hb)

    def test_negative_sequence_rejected(self):
        hb = dict(BASE, sequence=-1)
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(hb)

    def test_bad_version_rejected(self):
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(dict(BASE, version="0.2"))

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(dict(BASE, observed_at="2026-09-04T02:40:00"))

    def test_invalid_calendar_timestamp_rejected(self):
        with self.assertRaises(HeartbeatError):
            validate_heartbeat(dict(BASE, observed_at="2026-02-30T02:40:00Z"))

    def test_bool_threshold_rejected(self):
        with self.assertRaises(HeartbeatError):
            evaluate_freshness(BASE, now=NOW, healthy_within_seconds=True, degraded_within_seconds=60)

    def test_zero_threshold_rejected(self):
        with self.assertRaises(HeartbeatError):
            evaluate_freshness(BASE, now=NOW, healthy_within_seconds=0, degraded_within_seconds=60)

    def test_degraded_threshold_cannot_be_lower(self):
        with self.assertRaises(HeartbeatError):
            evaluate_freshness(BASE, now=NOW, healthy_within_seconds=60, degraded_within_seconds=30)

    def test_explicit_now_timezone_offset_supported(self):
        result = evaluate_freshness(
            BASE,
            now="2026-09-04T10:40:30+08:00",
            healthy_within_seconds=30,
            degraded_within_seconds=60,
        )
        self.assertEqual(result["status"], "HEALTHY")

    def test_fractional_seconds_are_deterministic(self):
        hb = dict(BASE, observed_at="2026-09-04T02:40:00.500000Z")
        result = evaluate_freshness(hb, now=NOW, healthy_within_seconds=30, degraded_within_seconds=60)
        self.assertEqual(result["age_seconds"], 29.5)


if __name__ == "__main__":
    unittest.main()
