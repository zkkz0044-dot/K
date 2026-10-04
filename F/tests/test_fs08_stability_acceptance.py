from __future__ import annotations
import gc,hashlib,json,os,tempfile,unittest,uuid
from pathlib import Path
from kk_f.release_activation import _switch,activate_candidate,initialize_current
from kk_f.release_manifest import validate_release_manifest
from kk_f.release_recovery import reconcile_release
from kk_f.release_staging import stage_release
from kk_f.release_state import commit_candidate,declare_candidate,initialize_release_state,read_release_state
from kk_f.release_tree import verify_release_tree
from kk_f.safety_state import SafetyStateError,clear_safe_mode,guarded_reconcile,initialize_safety_state,read_safety_state

def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def rid(n):return str(uuid.uuid5(uuid.NAMESPACE_URL,f"kk-f-fs08-{n}"))
def make_source(root,release_id,payload):
    root.mkdir(parents=True);files={"kk_f/__init__.py":b"","kk_f/main.py":payload}
    for rel,data in files.items():p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    records=[{"path":p,"sha256":hashlib.sha256(d).hexdigest(),"size":len(d)} for p,d in sorted(files.items())]
    m={"version":"0.1","release_id":release_id,"entrypoint":"kk_f/main.py","files":records,"manifest_sha256":""};m["manifest_sha256"]=hashlib.sha256(canonical({k:m[k] for k in ("version","release_id","entrypoint","files")})).hexdigest();return validate_release_manifest(m)
def identity(m):return {"release_id":m["release_id"],"manifest_sha256":m["manifest_sha256"]}
def install_initial(base,n=0):
    store=base/"store";ptr=base/"ptr";state=base/"state";sources=base/"sources";store.mkdir();ptr.mkdir();sources.mkdir();r=rid(n);m=make_source(sources/r,r,f"release-{n}\n".encode());stage_release(sources/r,m,store);initialize_release_state(state,identity(m));initialize_current(ptr,r);return store,ptr,state,sources,m

def temp_artifacts(root):
    bad=[]
    for p in root.rglob('*'):
        if p.name.startswith('.stage-') or p.name.startswith('.current-') or p.name.endswith('.tmp'):bad.append(p)
    return bad

class FS08StabilityTests(unittest.TestCase):
    def test_100_consecutive_release_lifecycle_cycles(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);store,ptr,state,sources,active=install_initial(base,0)
            for n in range(1,101):
                old=active; r=rid(n);active=make_source(sources/r,r,f"release-{n}\n".encode());stage_release(sources/r,active,store);declare_candidate(state,identity(active));s=activate_candidate(store,ptr,state,active)
                self.assertEqual(s["active"],identity(active));self.assertEqual(s["last_known_good"],identity(old));self.assertIsNone(s["candidate"]);self.assertEqual(os.readlink(ptr/"current"),r);verify_release_tree(store/r,active)
            self.assertEqual(read_release_state(state)["generation"],200);self.assertEqual(temp_artifacts(base),[])
    def test_100_interrupted_activation_recoveries_both_windows(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);store,ptr,state,sources,active=install_initial(base,1000);registry={active["release_id"]:active}
            for n in range(1,101):
                new=make_source(sources/rid(1000+n),rid(1000+n),f"crash-{n}\n".encode());registry[new["release_id"]]=new;stage_release(sources/new["release_id"],new,store);declare_candidate(state,identity(new));old=active
                if n%2:
                    _switch(ptr,new["release_id"]);r=reconcile_release(store,ptr,state,registry);self.assertEqual(r["action"],"RESTORED_ACTIVE_POINTER");self.assertEqual(os.readlink(ptr/"current"),old["release_id"]);activate_candidate(store,ptr,state,new)
                else:
                    commit_candidate(state);self.assertEqual(os.readlink(ptr/"current"),old["release_id"]);r=reconcile_release(store,ptr,state,registry);self.assertEqual(r["action"],"RESTORED_ACTIVE_POINTER");self.assertEqual(os.readlink(ptr/"current"),new["release_id"])
                active=new;self.assertEqual(read_release_state(state)["active"],identity(active))
            self.assertEqual(temp_artifacts(base),[])
    def test_50_corrupt_active_rollbacks_to_verified_lkg(self):
        for i in range(50):
            with tempfile.TemporaryDirectory() as td:
                base=Path(td);store,ptr,state,sources,a=install_initial(base,2000+i*2);b=make_source(sources/rid(2001+i*2),rid(2001+i*2),b"B");stage_release(sources/b["release_id"],b,store);declare_candidate(state,identity(b));activate_candidate(store,ptr,state,b);(store/b["release_id"]/"kk_f/main.py").write_bytes(b"CORRUPT");r=reconcile_release(store,ptr,state,{a["release_id"]:a,b["release_id"]:b});s=read_release_state(state);self.assertEqual(r["action"],"ROLLED_BACK_TO_LKG");self.assertEqual(s["active"],identity(a));self.assertEqual(os.readlink(ptr/"current"),a["release_id"])
    def test_50_safe_mode_latch_hold_clear_cycles_real_failures(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);store,ptr,state,sources,a=install_initial(base,4000);safe=base/"safe";initialize_safety_state(safe);(store/a["release_id"]/"kk_f/main.py").write_bytes(b"CORRUPT")
            registry={a["release_id"]:a}
            for _ in range(50):
                for _ in range(2):
                    with self.assertRaises(SafetyStateError):guarded_reconcile(safe,store,ptr,state,registry,failure_threshold=3)
                entered=guarded_reconcile(safe,store,ptr,state,registry,failure_threshold=3);self.assertEqual(entered["action"],"ENTERED_SAFE_MODE");before=read_safety_state(safe);held=guarded_reconcile(safe,store,ptr,state,registry,failure_threshold=3);self.assertEqual(held["action"],"HOLD_SAFE_MODE");self.assertEqual(read_safety_state(safe),before);clear_safe_mode(safe,expected_generation=before["generation"],acknowledge=True)
            self.assertEqual(read_safety_state(safe)["mode"],"NORMAL")
    def test_fd_and_temp_artifact_hygiene(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);store,ptr,state,sources,a=install_initial(base,5000);registry={a["release_id"]:a};gc.collect();before=len(os.listdir('/proc/self/fd'))
            for _ in range(300):read_release_state(state);verify_release_tree(store/a["release_id"],a);reconcile_release(store,ptr,state,registry)
            gc.collect();after=len(os.listdir('/proc/self/fd'));self.assertLessEqual(after,before+1);self.assertEqual(temp_artifacts(base),[])
if __name__=='__main__':unittest.main()
