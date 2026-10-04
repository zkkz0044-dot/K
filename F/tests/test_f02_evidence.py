import copy
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.evidence import EvidenceError, GENESIS_HASH, append, initialize, verify

BASE = {
    "protocol_version": "0.1",
    "message_id": "123e4567-e89b-42d3-a456-426614174000",
    "kind": "result",
    "source_role": "worker",
    "target_role": "supervisor",
    "timestamp": "2026-09-04T01:45:00Z",
    "status": "HEALTHY",
    "payload": {"case": "f02"},
    "error": None,
}


class F02EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "store"

    def tearDown(self):
        self.tmp.cleanup()

    def test_initialize_empty_store_verifies(self):
        initialize(self.root)
        self.assertEqual(verify(self.root), {"version": "0.1", "count": 0, "last_hash": GENESIS_HASH})

    def test_initialize_refuses_existing_store(self):
        initialize(self.root)
        with self.assertRaises(EvidenceError):
            initialize(self.root)

    def test_append_one_record_verifies(self):
        initialize(self.root)
        digest = append(self.root, copy.deepcopy(BASE))
        state = verify(self.root)
        self.assertEqual(state["count"], 1)
        self.assertEqual(state["last_hash"], digest)

    def test_multiple_records_chain_and_sequence(self):
        initialize(self.root)
        first = copy.deepcopy(BASE)
        second = copy.deepcopy(BASE)
        second["message_id"] = "223e4567-e89b-42d3-a456-426614174000"
        append(self.root, first)
        append(self.root, second)
        self.assertEqual(verify(self.root)["count"], 2)

    def test_invalid_f01_record_rejected_without_mutation(self):
        initialize(self.root)
        bad = copy.deepcopy(BASE)
        bad["status"] = "OK"
        with self.assertRaises(EvidenceError):
            append(self.root, bad)
        self.assertEqual(verify(self.root)["count"], 0)

    def test_payload_not_json_serializable_rejected_without_mutation(self):
        initialize(self.root)
        bad = copy.deepcopy(BASE)
        bad["payload"]["x"] = {1, 2}
        with self.assertRaises(EvidenceError):
            append(self.root, bad)
        self.assertEqual(verify(self.root)["count"], 0)

    def test_tampered_record_detected(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        log = self.root / "evidence.jsonl"
        entry = json.loads(log.read_text())
        entry["record"]["payload"]["case"] = "tampered"
        log.write_text(json.dumps(entry, separators=(",", ":")) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_tampered_hash_detected(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        log = self.root / "evidence.jsonl"
        entry = json.loads(log.read_text())
        entry["record_hash"] = "f" * 64
        log.write_text(json.dumps(entry, separators=(",", ":")) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_truncated_log_detected_by_head(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        (self.root / "evidence.jsonl").write_text("")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_head_rollback_detected(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        head = {"version": "0.1", "count": 0, "last_hash": GENESIS_HASH}
        (self.root / "HEAD.json").write_text(json.dumps(head) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_sequence_tamper_detected(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        log = self.root / "evidence.jsonl"
        entry = json.loads(log.read_text())
        entry["seq"] = 2
        log.write_text(json.dumps(entry) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_unknown_entry_field_rejected(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        log = self.root / "evidence.jsonl"
        entry = json.loads(log.read_text())
        entry["extra"] = True
        log.write_text(json.dumps(entry) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_duplicate_json_key_rejected(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        log = self.root / "evidence.jsonl"
        raw = log.read_text().rstrip("\n")
        raw = raw[:-1] + ',"seq":1}'
        log.write_text(raw + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_blank_line_rejected(self):
        initialize(self.root)
        (self.root / "evidence.jsonl").write_text("\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_missing_head_rejected(self):
        initialize(self.root)
        (self.root / "HEAD.json").unlink()
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_missing_log_rejected(self):
        initialize(self.root)
        (self.root / "evidence.jsonl").unlink()
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_head_unknown_field_rejected(self):
        initialize(self.root)
        head_path = self.root / "HEAD.json"
        head = json.loads(head_path.read_text())
        head["extra"] = 1
        head_path.write_text(json.dumps(head) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_append_refuses_corrupt_existing_chain(self):
        initialize(self.root)
        append(self.root, copy.deepcopy(BASE))
        (self.root / "evidence.jsonl").write_text("garbage\n")
        with self.assertRaises(EvidenceError):
            append(self.root, copy.deepcopy(BASE))

    def test_nonfinite_number_rejected(self):
        initialize(self.root)
        bad = copy.deepcopy(BASE)
        bad["payload"]["x"] = float("nan")
        with self.assertRaises(EvidenceError):
            append(self.root, bad)
        self.assertEqual(verify(self.root)["count"], 0)


if __name__ == "__main__":
    unittest.main()
