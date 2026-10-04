import json
import tempfile
import unittest
from pathlib import Path

from kk_k.test_support import project_tempdir
from kk_k.memory import MemoryError, append_event, load_goal, verify_event_log, write_goal_atomic


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = project_tempdir()
        self.root = Path(self.tmp.name)
        self.goal = self.root / "goal.json"
        self.log = self.root / "events.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_goal_roundtrip(self):
        value = {"schema":"K02.GOAL.1","goal_id":"g1","text":"inspect state","status":"ACTIVE"}
        write_goal_atomic(str(self.goal), value)
        self.assertEqual(load_goal(str(self.goal)), value)

    def test_goal_rejects_extra_field(self):
        bad = {"schema":"K02.GOAL.1","goal_id":"g1","text":"x","status":"ACTIVE","extra":1}
        with self.assertRaises(MemoryError): write_goal_atomic(str(self.goal), bad)

    def test_goal_rejects_wrong_type(self):
        bad = {"schema":"K02.GOAL.1","goal_id":"g1","text":"x","status":1}
        with self.assertRaises(MemoryError): write_goal_atomic(str(self.goal), bad)

    def test_event_chain_roundtrip(self):
        append_event(str(self.log), event_id="e1", kind="DECISION", subject="s1", summary="a")
        append_event(str(self.log), event_id="e2", kind="EXECUTION", subject="s2", summary="b")
        items = verify_event_log(str(self.log))
        self.assertEqual([x["sequence"] for x in items], [1,2])
        self.assertEqual(items[1]["prev_sha256"], items[0]["entry_sha256"])

    def test_event_tamper_detected(self):
        append_event(str(self.log), event_id="e1", kind="DECISION", subject="s1", summary="a")
        text = self.log.read_text(encoding="utf-8").replace('"summary":"a"','"summary":"x"')
        self.log.write_text(text, encoding="utf-8")
        with self.assertRaises(MemoryError): verify_event_log(str(self.log))

    def test_event_reorder_detected(self):
        append_event(str(self.log), event_id="e1", kind="DECISION", subject="s1", summary="a")
        append_event(str(self.log), event_id="e2", kind="EXECUTION", subject="s2", summary="b")
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.log.write_text(lines[1] + "\n" + lines[0] + "\n", encoding="utf-8")
        with self.assertRaises(MemoryError): verify_event_log(str(self.log))

    def test_event_middle_delete_detected(self):
        for i in range(1,4):
            append_event(str(self.log), event_id=f"e{i}", kind="SYSTEM", subject="s", summary=str(i))
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.log.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
        with self.assertRaises(MemoryError): verify_event_log(str(self.log))

    def test_unterminated_record_rejected(self):
        append_event(str(self.log), event_id="e1", kind="SYSTEM", subject="s", summary="x")
        self.log.write_bytes(self.log.read_bytes().rstrip(b"\n"))
        with self.assertRaises(MemoryError): verify_event_log(str(self.log))

    def test_oversize_summary_rejected(self):
        with self.assertRaises(MemoryError):
            append_event(str(self.log), event_id="e1", kind="SYSTEM", subject="s", summary="x"*3000)

    def test_invalid_kind_rejected(self):
        with self.assertRaises(MemoryError):
            append_event(str(self.log), event_id="e1", kind="RUN_SHELL", subject="s", summary="x")

    def test_empty_log_valid(self):
        self.assertEqual(verify_event_log(str(self.log)), [])

if __name__ == "__main__":
    unittest.main()
