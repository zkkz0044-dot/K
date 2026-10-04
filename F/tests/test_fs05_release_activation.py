from __future__ import annotations
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest import mock
from kk_f.release_activation import *
from kk_f.release_activation import _switch
from kk_f.release_state import initialize_release_state,declare_candidate,read_release_state,ReleaseStateError
from kk_f.release_store_guard import seal_private_stage

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def make_release(root,rid,body):
    root.mkdir(); files={"kk_f/main.py":body};
    for rel,data in files.items(): p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    rec=[{"path":p,"sha256":hashlib.sha256(d).hexdigest(),"size":len(d)} for p,d in sorted(files.items())];m={"version":"0.1","release_id":rid,"entrypoint":"kk_f/main.py","files":rec,"manifest_sha256":""};m["manifest_sha256"]=hashlib.sha256(canonical({k:m[k] for k in ("version","release_id","entrypoint","files")})).hexdigest();seal_private_stage(root,root.stat().st_dev);return m
class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory();b=Path(self.td.name);self.store=b/"store";self.ptr=b/"ptr";self.state=b/"state";self.store.mkdir();self.ptr.mkdir()
        self.aid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";self.bid="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";self.am=make_release(self.store/self.aid,self.aid,b"A");self.bm=make_release(self.store/self.bid,self.bid,b"B")
        initialize_release_state(self.state,{"release_id":self.aid,"manifest_sha256":self.am["manifest_sha256"]});initialize_current(self.ptr,self.aid);declare_candidate(self.state,{"release_id":self.bid,"manifest_sha256":self.bm["manifest_sha256"]})
    def tearDown(self): self.td.cleanup()
    def test_initialize_current_rejects_noncanonical_release_id(self):
        d=Path(self.td.name)/"otherptr";d.mkdir()
        for bad in ("x","AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA","../x",123):
            self.assertRaises(ReleaseActivationError,initialize_current,d,bad)
            self.assertFalse((d/"current").exists() or (d/"current").is_symlink())
    def test_activation_switches_pointer_and_commits_state(self):
        s=activate_candidate(self.store,self.ptr,self.state,self.bm);self.assertEqual((self.ptr/"current").readlink().as_posix(),self.bid);self.assertEqual(s["active"]["release_id"],self.bid);self.assertEqual(s["last_known_good"]["release_id"],self.aid);self.assertIsNone(s["candidate"]);self.assertEqual(s["generation"],2)
    def test_manifest_must_match_authoritative_candidate(self):
        self.assertRaises(ReleaseActivationError,activate_candidate,self.store,self.ptr,self.state,self.am);self.assertEqual((self.ptr/"current").readlink().as_posix(),self.aid)
    def test_current_pointer_must_match_authoritative_active(self):
        (self.ptr/"current").unlink();(self.ptr/"current").symlink_to(self.bid);self.assertRaises(ReleaseActivationError,activate_candidate,self.store,self.ptr,self.state,self.bm);self.assertEqual(read_release_state(self.state)["active"]["release_id"],self.aid)
    def test_absolute_or_nested_current_target_rejected(self):
        for target in ("/tmp/x","a/b","../x"):
            (self.ptr/"current").unlink();(self.ptr/"current").symlink_to(target);self.assertRaises(ReleaseActivationError,activate_candidate,self.store,self.ptr,self.state,self.bm)
            (self.ptr/"current").unlink();(self.ptr/"current").symlink_to(self.aid)
    def test_tampered_candidate_blocks_before_pointer_change(self):
        (self.store/self.bid/"kk_f/main.py").write_bytes(b"X");self.assertRaises(ReleaseActivationError,activate_candidate,self.store,self.ptr,self.state,self.bm);self.assertEqual((self.ptr/"current").readlink().as_posix(),self.aid)
    def test_state_commit_failure_restores_old_pointer(self):
        before=read_release_state(self.state)
        with mock.patch("kk_f.release_activation.commit_candidate",side_effect=ReleaseStateError("boom")): self.assertRaises(ReleaseActivationError,activate_candidate,self.store,self.ptr,self.state,self.bm)
        self.assertEqual((self.ptr/"current").readlink().as_posix(),self.aid);self.assertEqual(read_release_state(self.state),before)
    def test_state_commit_and_pointer_restore_failure_fails_loudly(self):
        real=_switch; calls={"n":0}
        def flaky(root,rid):
            calls["n"]+=1
            if calls["n"]==2: raise ReleaseActivationError("restore boom")
            return real(root,rid)
        with mock.patch("kk_f.release_activation.commit_candidate",side_effect=ReleaseStateError("boom")),mock.patch("kk_f.release_activation._switch",side_effect=flaky):
            with self.assertRaisesRegex(ReleaseActivationError,"restoration failed"): activate_candidate(self.store,self.ptr,self.state,self.bm)
        self.assertEqual((self.ptr/"current").readlink().as_posix(),self.bid);self.assertEqual(read_release_state(self.state)["active"]["release_id"],self.aid)
    def test_release_bytes_unchanged(self):
        before=(self.store/self.bid/"kk_f/main.py").read_bytes();activate_candidate(self.store,self.ptr,self.state,self.bm);self.assertEqual((self.store/self.bid/"kk_f/main.py").read_bytes(),before)
if __name__=='__main__':unittest.main()
