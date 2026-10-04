from __future__ import annotations
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest import mock
from kk_f.release_activation import initialize_current,_switch,ReleaseActivationError
from kk_f.release_recovery import *
from kk_f.release_state import initialize_release_state,declare_candidate,commit_candidate,read_release_state,ReleaseStateError
from kk_f.release_store_guard import seal_private_stage

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def release(root,rid,data):
    root.mkdir();p=root/"app";p.write_bytes(data);files=[{"path":"app","sha256":hashlib.sha256(data).hexdigest(),"size":len(data)}];m={"version":"0.1","release_id":rid,"entrypoint":"app","files":files,"manifest_sha256":""};m["manifest_sha256"]=hashlib.sha256(canonical({k:m[k] for k in ("version","release_id","entrypoint","files")})).hexdigest();seal_private_stage(root,root.stat().st_dev);return m
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory();b=Path(self.td.name);self.store=b/"store";self.ptr=b/"ptr";self.state=b/"state";self.store.mkdir();self.ptr.mkdir();self.a="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";self.b="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";self.am=release(self.store/self.a,self.a,b"A");self.bm=release(self.store/self.b,self.b,b"B");self.reg={self.a:self.am,self.b:self.bm};initialize_release_state(self.state,{"release_id":self.a,"manifest_sha256":self.am["manifest_sha256"]});initialize_current(self.ptr,self.a);declare_candidate(self.state,{"release_id":self.b,"manifest_sha256":self.bm["manifest_sha256"]})
    def tearDown(self): self.td.cleanup()
    def test_consistent_pending_candidate_no_action(self): self.assertEqual(reconcile_release(self.store,self.ptr,self.state,self.reg)["action"],"NO_ACTION");self.assertEqual(read_release_state(self.state)["candidate"]["release_id"],self.b)
    def test_crash_after_pointer_switch_before_commit_restores_active_not_promote_candidate(self):
        _switch(self.ptr,self.b);r=reconcile_release(self.store,self.ptr,self.state,self.reg);self.assertEqual(r["action"],"RESTORED_ACTIVE_POINTER");self.assertEqual((self.ptr/"current").readlink().as_posix(),self.a);self.assertEqual(read_release_state(self.state)["active"]["release_id"],self.a);self.assertEqual(read_release_state(self.state)["candidate"]["release_id"],self.b)
    def test_crash_after_state_commit_before_pointer_switch_repairs_to_committed_active(self):
        commit_candidate(self.state);self.assertEqual((self.ptr/"current").readlink().as_posix(),self.a);r=reconcile_release(self.store,self.ptr,self.state,self.reg);self.assertEqual(r["action"],"RESTORED_ACTIVE_POINTER");self.assertEqual((self.ptr/"current").readlink().as_posix(),self.b)
    def test_malformed_pointer_repaired_when_active_verified(self):
        (self.ptr/"current").unlink();(self.ptr/"current").write_text("bad");r=reconcile_release(self.store,self.ptr,self.state,self.reg);self.assertEqual(r["action"],"RESTORED_ACTIVE_POINTER");self.assertTrue((self.ptr/"current").is_symlink());self.assertEqual((self.ptr/"current").readlink().as_posix(),self.a)
    def test_corrupt_active_rolls_back_to_verified_lkg_after_prior_commit(self):
        commit_candidate(self.state);_switch(self.ptr,self.b);(self.store/self.b/"app").write_bytes(b"BAD");r=reconcile_release(self.store,self.ptr,self.state,self.reg);s=read_release_state(self.state);self.assertEqual(r["action"],"ROLLED_BACK_TO_LKG");self.assertEqual(s["active"]["release_id"],self.a);self.assertEqual(s["last_known_good"]["release_id"],self.a);self.assertIsNone(s["candidate"]);self.assertEqual((self.ptr/"current").readlink().as_posix(),self.a)
    def test_corrupt_active_and_no_distinct_lkg_fails_closed(self):
        (self.store/self.a/"app").write_bytes(b"BAD");self.assertRaises(ReleaseRecoveryError,reconcile_release,self.store,self.ptr,self.state,self.reg);self.assertEqual(read_release_state(self.state)["active"]["release_id"],self.a)
    def test_manifest_identity_mismatch_cannot_receive_recovery_credit(self):
        bad=dict(self.reg);bad[self.a]=self.bm;self.assertRaises(ReleaseRecoveryError,reconcile_release,self.store,self.ptr,self.state,bad)
    def test_writable_lkg_metadata_cannot_receive_recovery_credit(self):
        commit_candidate(self.state); _switch(self.ptr,self.b)
        (self.store/self.b/"app").write_bytes(b"BAD")
        os.chmod(self.store/self.a/"app",0o644)
        with self.assertRaises(ReleaseRecoveryError): reconcile_release(self.store,self.ptr,self.state,self.reg)
        self.assertEqual(read_release_state(self.state)["active"]["release_id"],self.b)

    def test_rollback_pointer_failure_leaves_committed_lkg_authority_for_retry(self):
        commit_candidate(self.state);_switch(self.ptr,self.b);(self.store/self.b/"app").write_bytes(b"BAD")
        with mock.patch("kk_f.release_recovery._switch",side_effect=ReleaseActivationError("boom")):
            with self.assertRaisesRegex(ReleaseRecoveryError,"authority committed"):
                reconcile_release(self.store,self.ptr,self.state,self.reg)
        s=read_release_state(self.state);self.assertEqual(s["active"]["release_id"],self.a);self.assertEqual((self.ptr/"current").readlink().as_posix(),self.b)
        r=reconcile_release(self.store,self.ptr,self.state,self.reg);self.assertEqual(r["action"],"RESTORED_ACTIVE_POINTER");self.assertEqual((self.ptr/"current").readlink().as_posix(),self.a)
if __name__=='__main__':unittest.main()
