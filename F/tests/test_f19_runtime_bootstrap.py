import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.frozen_authority import build_frozen_authority

from kk_f.runtime_bootstrap import RuntimeBootstrapError, bootstrap_runtime
from kk_f.restart_ledger import read_ledger


class F19RuntimeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.cwd=self.root/'work';self.cwd.mkdir();self.ledger=self.root/'ledger';self.exe=self.root/'worker.py'
        self.exe.write_text("#!/usr/bin/python3\nimport pathlib,time\npathlib.Path('started').write_text('yes')\ntime.sleep(5)\n");self.exe.chmod(0o700)
        self.digest=hashlib.sha256(self.exe.read_bytes()).hexdigest();self.auth=self.root/'authority.json'
        self.manifest=build_frozen_authority('kk-f-root',self.spec(),2)
        self.auth.write_text(json.dumps(self.manifest,separators=(',',':'))+'\n');self.auth.chmod(0o600);self.handles=[];self.locks=[]
    def tearDown(self):
        for h in self.handles:
            try:h.stop(grace_seconds=0.05)
            except Exception:pass
        for lock in self.locks:
            try:lock.release()
            except Exception:pass
        self.tmp.cleanup()
    def spec(self,**updates):
        s={'version':'0.1','executable':str(self.exe),'argv':[],'cwd':str(self.cwd),'env':{},'sha256':self.digest};s.update(updates);return s
    def boot(self,spec=None):
        r=bootstrap_runtime(str(self.auth),str(self.ledger),self.spec() if spec is None else spec);self.handles.append(r.worker);self.locks.append(r.instance_lock);return r

    def test_exact_authorized_candidate_launches_real_worker(self):
        r=self.boot();self.assertEqual(r.authority_id,'kk-f-root');self.assertGreater(r.worker.pid,0);self.assertEqual(r.worker.observe()['status'],'RUNNING')
    def test_restart_budget_comes_only_from_authority(self):
        r=self.boot();ledger=read_ledger(str(self.ledger));self.assertEqual(r.max_restart_attempts,2);self.assertEqual(ledger['max_attempts'],2);self.assertEqual(ledger['attempts'],0)
    def test_initial_running_worker_is_not_claimed_healthy(self):
        r=self.boot();self.assertEqual(r.worker.observe()['status'],'RUNNING');self.assertNotEqual(r.worker.observe()['status'],'HEALTHY')
    def test_unauthorized_digest_denied_before_ledger_creation(self):
        with self.assertRaises(RuntimeBootstrapError):self.boot(self.spec(sha256='f'*64))
        self.assertFalse(self.ledger.exists());self.assertFalse((self.cwd/'started').exists())
    def test_unauthorized_executable_denied_before_ledger_creation(self):
        other=self.root/'other.py';other.write_text('#!/usr/bin/python3\n');other.chmod(0o700)
        with self.assertRaises(RuntimeBootstrapError):self.boot(self.spec(executable=str(other)))
        self.assertFalse(self.ledger.exists())
    def test_mutable_authority_denied_before_ledger_creation(self):
        self.auth.chmod(0o622)
        with self.assertRaises(RuntimeBootstrapError):self.boot()
        self.assertFalse(self.ledger.exists())
    def test_candidate_content_change_after_manifest_blocks_launch(self):
        self.exe.write_text(self.exe.read_text()+'#tampered\n')
        with self.assertRaises(RuntimeBootstrapError):self.boot()
        self.assertFalse(self.ledger.exists());self.assertFalse((self.cwd/'started').exists())
    def test_preexisting_ledger_blocks_second_bootstrap(self):
        first=self.boot();pid=first.worker.pid
        with self.assertRaises(RuntimeBootstrapError):bootstrap_runtime(str(self.auth),str(self.ledger),self.spec())
        self.assertEqual(first.worker.pid,pid);self.assertEqual(first.worker.observe()['status'],'RUNNING')
    def test_authority_budget_bool_rejected(self):
        bad=dict(self.manifest,max_restart_attempts=True);self.auth.write_text(json.dumps(bad));self.auth.chmod(0o600)
        with self.assertRaises(RuntimeBootstrapError):self.boot()
        self.assertFalse(self.ledger.exists())


if __name__=='__main__':unittest.main()
