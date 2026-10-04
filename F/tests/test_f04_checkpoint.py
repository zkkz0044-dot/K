import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.checkpoint import CheckpointError, read_checkpoint, write_checkpoint


class F04CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_checkpoint_fails_closed(self):
        with self.assertRaises(CheckpointError):
            read_checkpoint(self.root)

    def test_write_then_read_roundtrip(self):
        digest = write_checkpoint(self.root, 0, "READY", {"task": "x"})
        value = read_checkpoint(self.root)
        self.assertEqual(value["generation"], 0)
        self.assertEqual(value["status"], "READY")
        self.assertEqual(value["checksum"], digest)

    def test_generation_must_increase(self):
        write_checkpoint(self.root, 2, "RUNNING", {})
        for generation in (2, 1, 0):
            with self.subTest(generation=generation):
                with self.assertRaises(CheckpointError):
                    write_checkpoint(self.root, generation, "RUNNING", {})
        self.assertEqual(read_checkpoint(self.root)["generation"], 2)

    def test_higher_generation_replaces_checkpoint(self):
        write_checkpoint(self.root, 0, "READY", {"a": 1})
        write_checkpoint(self.root, 1, "RUNNING", {"a": 2})
        value = read_checkpoint(self.root)
        self.assertEqual(value["generation"], 1)
        self.assertEqual(value["payload"], {"a": 2})

    def test_invalid_status_rejected_without_mutation(self):
        write_checkpoint(self.root, 0, "READY", {})
        before = (self.root / "checkpoint.json").read_bytes()
        with self.assertRaises(CheckpointError):
            write_checkpoint(self.root, 1, "UNKNOWN", {})
        self.assertEqual((self.root / "checkpoint.json").read_bytes(), before)

    def test_payload_must_be_object(self):
        for payload in (None, [], "x", 1):
            with self.subTest(payload=payload):
                with self.assertRaises(CheckpointError):
                    write_checkpoint(self.root, 0, "READY", payload)

    def test_nonfinite_payload_rejected(self):
        with self.assertRaises(CheckpointError):
            write_checkpoint(self.root, 0, "READY", {"x": float("nan")})

    def test_type_confused_generation_rejected(self):
        for value in (True, 1.0, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(CheckpointError):
                    write_checkpoint(self.root, value, "READY", {})

    def test_checksum_tamper_detected(self):
        write_checkpoint(self.root, 0, "READY", {"a": 1})
        path = self.root / "checkpoint.json"
        value = json.loads(path.read_text())
        value["payload"]["a"] = 2
        path.write_text(json.dumps(value) + "\n")
        with self.assertRaises(CheckpointError):
            read_checkpoint(self.root)

    def test_unknown_field_rejected(self):
        write_checkpoint(self.root, 0, "READY", {})
        path = self.root / "checkpoint.json"
        value = json.loads(path.read_text())
        value["extra"] = 1
        path.write_text(json.dumps(value) + "\n")
        with self.assertRaises(CheckpointError):
            read_checkpoint(self.root)

    def test_duplicate_key_rejected(self):
        self.root.mkdir(parents=True)
        raw = '{"version":"0.1","generation":0,"generation":0,"status":"READY","payload":{},"checksum":"0"}\n'
        (self.root / "checkpoint.json").write_text(raw)
        with self.assertRaises(CheckpointError):
            read_checkpoint(self.root)

    def test_unsupported_version_rejected(self):
        write_checkpoint(self.root, 0, "READY", {})
        path = self.root / "checkpoint.json"
        value = json.loads(path.read_text())
        value["version"] = "9.9"
        path.write_text(json.dumps(value) + "\n")
        with self.assertRaises(CheckpointError):
            read_checkpoint(self.root)

    def test_corrupt_existing_checkpoint_blocks_new_write(self):
        write_checkpoint(self.root, 0, "READY", {})
        path = self.root / "checkpoint.json"
        path.write_text("garbage\n")
        with self.assertRaises(CheckpointError):
            write_checkpoint(self.root, 1, "RUNNING", {})
        self.assertEqual(path.read_text(), "garbage\n")

    def test_failed_atomic_replace_preserves_previous_checkpoint(self):
        write_checkpoint(self.root, 0, "READY", {"stable": True})
        before = (self.root / "checkpoint.json").read_bytes()
        with mock.patch("kk_f.checkpoint.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(OSError):
                write_checkpoint(self.root, 1, "RUNNING", {"stable": False})
        self.assertEqual((self.root / "checkpoint.json").read_bytes(), before)
        self.assertFalse((self.root / "checkpoint.json.tmp").exists())
        self.assertEqual(read_checkpoint(self.root)["generation"], 0)

    def test_generation_and_status_are_part_of_checksum(self):
        write_checkpoint(self.root, 0, "READY", {})
        path = self.root / "checkpoint.json"
        original = json.loads(path.read_text())
        for key, value in (("generation", 1), ("status", "RUNNING")):
            changed = copy.deepcopy(original)
            changed[key] = value
            path.write_text(json.dumps(changed) + "\n")
            with self.assertRaises(CheckpointError):
                read_checkpoint(self.root)


if __name__ == "__main__":
    unittest.main()
