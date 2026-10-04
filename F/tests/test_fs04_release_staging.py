from __future__ import annotations
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest import mock
from kk_f.release_staging import *
from kk_f.release_staging import _rename_noreplace

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def fixture(root):
    files={"kk_f/__init__.py":b"","kk_f/main.py":b"print('ok')\n"}
    for rel,data in files.items(): p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    rec=[{"path":p,"sha256":hashlib.sha256(d).hexdigest(),"size":len(d)} for p,d in sorted(files.items())]
    m={"version":"0.1","release_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","entrypoint":"kk_f/main.py","files":rec,"manifest_sha256":""}
    m["manifest_sha256"]=hashlib.sha256(canonical({k:m[k] for k in ("version","release_id","entrypoint","files")})).hexdigest();return m
class StagingTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); base=Path(self.td.name);self.src=base/"src";self.store=base/"store";self.src.mkdir();self.store.mkdir();self.m=fixture(self.src)
    def tearDown(self): self.td.cleanup()
    def test_exact_candidate_stages_and_reverifies(self):
        r=stage_release(self.src,self.m,self.store);self.assertEqual(r["release_id"],self.m["release_id"]);self.assertEqual(r["file_count"],2);self.assertTrue(Path(r["path"]).is_dir());self.assertFalse(any(p.name.startswith('.stage-') for p in self.store.iterdir()))
    def test_invalid_source_blocks_without_temp_or_final(self):
        (self.src/"kk_f/main.py").write_text("bad");self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,self.store);self.assertEqual(list(self.store.iterdir()),[])
    def test_invalid_manifest_blocks(self):
        bad=dict(self.m);bad["manifest_sha256"]="0"*64;self.assertRaises(ReleaseStagingError,stage_release,self.src,bad,self.store);self.assertEqual(list(self.store.iterdir()),[])
    def test_existing_final_never_overwritten(self):
        final=self.store/self.m["release_id"];final.mkdir();marker=final/"keep";marker.write_text("x");self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,self.store);self.assertEqual(marker.read_text(),"x")
    def test_relative_store_rejected(self): self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,"relative")
    def test_symlink_store_rejected(self):
        link=Path(self.td.name)/"link";link.symlink_to(self.store,target_is_directory=True);self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,link)
    def test_copy_failure_cleans_private_temp_and_no_final(self):
        with mock.patch("kk_f.release_staging._copy_declared",side_effect=ReleaseStagingError("boom")): self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,self.store)
        self.assertEqual(list(self.store.iterdir()),[])
    def test_postcopy_tamper_detected_before_publication(self):
        original=verify_release_tree
        calls={"n":0}
        def wrapped(root,m):
            calls["n"]+=1
            if calls["n"]==2: (Path(root)/"kk_f/main.py").write_text("tamper")
            return original(root,m)
        with mock.patch("kk_f.release_staging.verify_release_tree",side_effect=wrapped): self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,self.store)
        self.assertEqual(list(self.store.iterdir()),[])
    def test_rename_failure_cleans_temp_and_no_final(self):
        with mock.patch("kk_f.release_staging._rename_noreplace",side_effect=ReleaseStagingError("boom")): self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,self.store)
        self.assertEqual(list(self.store.iterdir()),[])
    def test_concurrent_destination_race_is_no_replace(self):
        real=_rename_noreplace
        def raced(src,dst):
            dst.mkdir()
            real(src,dst)
        with mock.patch("kk_f.release_staging._rename_noreplace",side_effect=raced):
            self.assertRaises(ReleaseStagingError,stage_release,self.src,self.m,self.store)
        final=self.store/self.m["release_id"]
        self.assertTrue(final.is_dir())
        self.assertEqual(list(final.iterdir()),[])
        self.assertFalse(any(p.name.startswith('.stage-') for p in self.store.iterdir()))
    def test_does_not_mutate_source(self):
        before={p.relative_to(self.src).as_posix():p.read_bytes() for p in self.src.rglob('*') if p.is_file()};stage_release(self.src,self.m,self.store);after={p.relative_to(self.src).as_posix():p.read_bytes() for p in self.src.rglob('*') if p.is_file()};self.assertEqual(before,after)
if __name__=='__main__':unittest.main()
