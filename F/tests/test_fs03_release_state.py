from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from unittest import mock
from kk_f.release_state import *

def ident(seed="a"):
    rid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" if seed=="a" else "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    return {"release_id":rid,"manifest_sha256":seed*64}

class ReleaseStateTests(unittest.TestCase):
    def setUp(self): self.td=tempfile.TemporaryDirectory(); self.root=Path(self.td.name)/"state"
    def tearDown(self): self.td.cleanup()
    def test_initialize_active_equals_lkg_candidate_null(self):
        s=initialize_release_state(self.root,ident()); self.assertEqual(s["generation"],0); self.assertEqual(s["active"],s["last_known_good"]); self.assertIsNone(s["candidate"]); self.assertEqual(read_release_state(self.root),s)
    def test_initialize_refuses_existing(self):
        initialize_release_state(self.root,ident()); self.assertRaises(ReleaseStateError,initialize_release_state,self.root,ident("b"))
    def test_declare_candidate_advances_only_candidate_and_generation(self):
        a=initialize_release_state(self.root,ident()); b=declare_candidate(self.root,ident("b")); self.assertEqual(b["generation"],1); self.assertEqual(b["active"],a["active"]); self.assertEqual(b["last_known_good"],a["last_known_good"]); self.assertEqual(b["candidate"],ident("b"))
    def test_candidate_cannot_equal_active_or_existing_candidate(self):
        initialize_release_state(self.root,ident()); self.assertRaises(ReleaseStateError,declare_candidate,self.root,ident()); declare_candidate(self.root,ident("b")); self.assertRaises(ReleaseStateError,declare_candidate,self.root,ident("b"))
    def test_clear_candidate_advances_and_preserves_authority(self):
        initialize_release_state(self.root,ident()); before=declare_candidate(self.root,ident("b")); after=clear_candidate(self.root); self.assertEqual(after["generation"],2); self.assertIsNone(after["candidate"]); self.assertEqual(after["active"],before["active"]); self.assertEqual(after["last_known_good"],before["last_known_good"])
    def test_clear_without_candidate_fails(self): initialize_release_state(self.root,ident()); self.assertRaises(ReleaseStateError,clear_candidate,self.root)
    def test_missing_corrupt_unknown_duplicate_fail_closed(self):
        self.assertRaises(ReleaseStateError,read_release_state,self.root); self.root.mkdir(); p=self.root/STATE_FILE
        for raw in ('{}','{"version":"0.1","version":"0.1"}','{"x":NaN}'):
            p.write_text(raw); self.assertRaises(ReleaseStateError,read_release_state,self.root)
    def test_checksum_tampering_detected(self):
        initialize_release_state(self.root,ident()); p=self.root/STATE_FILE; v=json.loads(p.read_text()); v["generation"]=9; p.write_text(json.dumps(v)); self.assertRaises(ReleaseStateError,read_release_state,self.root)
    def test_identity_schema_and_types_strict(self):
        bad=[None,{"release_id":"x","manifest_sha256":"a"*64},{"release_id":ident()["release_id"],"manifest_sha256":"A"*64},{"release_id":ident()["release_id"],"manifest_sha256":"a"*64,"x":1}]
        for v in bad: self.assertRaises(ReleaseStateError,initialize_release_state,self.root,v)
    def test_bool_generation_rejected(self):
        s=initialize_release_state(self.root,ident()); s["generation"]=True; self.assertRaises(ReleaseStateError,validate_release_state,s)
    def test_replace_failure_preserves_verified_previous(self):
        original=initialize_release_state(self.root,ident());
        with mock.patch("kk_f.release_state.os.replace",side_effect=OSError("boom")): self.assertRaises(ReleaseStateError,declare_candidate,self.root,ident("b"))
        self.assertEqual(read_release_state(self.root),original)
    def test_corrupt_existing_blocks_mutation(self):
        initialize_release_state(self.root,ident()); p=self.root/STATE_FILE; p.write_text("bad"); self.assertRaises(ReleaseStateError,declare_candidate,self.root,ident("b"))
    def test_exact_state_schema(self):
        s=initialize_release_state(self.root,ident()); s["extra"]=1; self.assertRaises(ReleaseStateError,validate_release_state,s)
    def test_invalid_utf8_rejected(self):
        self.root.mkdir(); (self.root/STATE_FILE).write_bytes(b"\xff"); self.assertRaises(ReleaseStateError,read_release_state,self.root)
if __name__=='__main__': unittest.main()
