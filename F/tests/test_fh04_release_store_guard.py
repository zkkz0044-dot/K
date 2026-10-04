from __future__ import annotations
import hashlib, json, os, pathlib, tempfile, unittest
from kk_f.release_manifest import validate_release_manifest
from kk_f.release_staging import ReleaseStagingError, stage_release
from kk_f.release_store_guard import ReleaseStoreGuardError, verify_published_release, verify_store_root

class FH04ReleaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(dir='/var/tmp'); self.root=pathlib.Path(self.td.name); os.chmod(self.root,0o755); self.source=self.root/'src'; self.store=self.root/'store'; self.source.mkdir(); self.store.mkdir(mode=0o755)
        (self.source/'kk_f').mkdir(); (self.source/'kk_f'/'main.py').write_text("print('ok')\n"); os.chmod(self.source/'kk_f'/'main.py',0o755)
        data=(self.source/'kk_f'/'main.py').read_bytes(); rid='12345678-1234-5678-9234-567812345678'
        m={'version':'0.1','release_id':rid,'entrypoint':'kk_f/main.py','files':[{'path':'kk_f/main.py','sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}],'manifest_sha256':''}
        material={k:m[k] for k in ('version','release_id','entrypoint','files')}; m['manifest_sha256']=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.manifest=m
    def tearDown(self):
        for p in self.root.rglob('*'):
            try: os.chmod(p,0o700 if p.is_dir() else 0o600)
            except OSError: pass
        self.td.cleanup()
    def test_stage_seals_root_owned_readonly_tree(self):
        out=stage_release(self.source,self.manifest,self.store); release=pathlib.Path(out['path']); verify_published_release(self.store,self.manifest['release_id'])
        f=release/'kk_f'/'main.py'; self.assertEqual(f.stat().st_uid,0); self.assertEqual(f.stat().st_mode & 0o222,0); self.assertEqual(f.stat().st_nlink,1); self.assertNotEqual(f.stat().st_mode & 0o111,0)
    def test_world_writable_store_rejected(self):
        os.chmod(self.store,0o777)
        with self.assertRaises(ReleaseStagingError): stage_release(self.source,self.manifest,self.store)

    def test_nonsticky_writable_ancestor_rejected(self):
        os.chmod(self.root,0o777)
        with self.assertRaises(ReleaseStagingError): stage_release(self.source,self.manifest,self.store)
        os.chmod(self.root,0o755)
    def test_nonroot_owned_store_rejected(self):
        os.chown(self.store,65534,65534)
        with self.assertRaises(ReleaseStagingError): stage_release(self.source,self.manifest,self.store)
        os.chown(self.store,0,0)
    def test_published_file_write_bit_drift_rejected(self):
        out=stage_release(self.source,self.manifest,self.store); f=pathlib.Path(out['path'])/'kk_f'/'main.py'; os.chmod(f,0o644)
        with self.assertRaises(ReleaseStoreGuardError): verify_published_release(self.store,self.manifest['release_id'])
    def test_published_hardlink_rejected(self):
        out=stage_release(self.source,self.manifest,self.store); f=pathlib.Path(out['path'])/'kk_f'/'main.py'; alias=self.root/'alias'; os.link(f,alias)
        with self.assertRaises(ReleaseStoreGuardError): verify_published_release(self.store,self.manifest['release_id'])
    def test_published_file_owner_drift_rejected(self):
        out=stage_release(self.source,self.manifest,self.store); f=pathlib.Path(out['path'])/'kk_f'/'main.py'; os.chown(f,65534,65534)
        with self.assertRaises(ReleaseStoreGuardError): verify_published_release(self.store,self.manifest['release_id'])

    def test_published_symlink_substitution_rejected(self):
        out=stage_release(self.source,self.manifest,self.store); f=pathlib.Path(out['path'])/'kk_f'/'main.py'; outside=self.root/'outside'; outside.write_text("print('ok')\n"); f.unlink(); f.symlink_to(outside)
        with self.assertRaises(ReleaseStoreGuardError): verify_published_release(self.store,self.manifest['release_id'])

    def test_runtime_identity_cannot_modify_sealed_release(self):
        out=stage_release(self.source,self.manifest,self.store); f=pathlib.Path(out['path'])/'kk_f'/'main.py'
        pid=os.fork()
        if pid==0:
            try:
                os.setgid(65534); os.setuid(65534); os.open(f,os.O_WRONLY); os._exit(9)
            except PermissionError: os._exit(0)
            except Exception: os._exit(8)
        _,status=os.waitpid(pid,0); self.assertEqual(os.waitstatus_to_exitcode(status),0)

if __name__=='__main__': unittest.main()
