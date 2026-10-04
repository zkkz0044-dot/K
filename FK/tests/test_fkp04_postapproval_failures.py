from __future__ import annotations
import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
for p in ('/root/K/F/src','/root/K/K/src'):
    if p not in sys.path: sys.path.insert(0,p)
from kk_f import fk_gateway
from kk_f.fk_approval import issue_a03_approval
from kk_k.verifier import verify_receipt

class FKP04PostApprovalFailureTests(unittest.TestCase):
    def _fixture(self, root:Path, *, bad_authority=False, tamper=False):
        script=root/'smoke.py'
        script.write_text('#!/usr/bin/python3\nraise SystemExit(0)\n',encoding='utf-8'); script.chmod(0o755)
        digest=hashlib.sha256(script.read_bytes()).hexdigest()
        spec={'version':'0.1','executable':str(script),'argv':[],'cwd':'/root/K/F','env':{},'sha256':digest}
        manifest=root/'authority.json'
        aid='wrong-authority' if bad_authority else 'fk-a03-smoke'
        manifest.write_text(json.dumps({'version':'0.2','authority_id':aid,'process_spec':spec,'max_restart_attempts':1},sort_keys=True,separators=(',',':'))+'\n')
        manifest.chmod(0o600)
        if tamper:
            script.write_text('#!/usr/bin/python3\nraise SystemExit(9)\n',encoding='utf-8'); script.chmod(0o755)
        return script,manifest

    def _approved_run(self, *, bad_authority=False, tamper=False):
        with tempfile.TemporaryDirectory(dir='/root/K/F') as ftd, tempfile.TemporaryDirectory(dir='/root/K/FK/.test_tmp') as atd:
            script,manifest=self._fixture(Path(ftd),bad_authority=bad_authority,tamper=tamper)
            approval=str(Path(atd)/'a03_approval.json')
            issue_a03_approval(ttl_seconds=10,now_epoch=100,path=approval,nonce='d'*32)
            with mock.patch.object(fk_gateway,'A03_AUTHORITY_PATH',str(manifest)), mock.patch.object(fk_gateway,'A03_EXPECTED_EXECUTABLE',str(script)):
                r=fk_gateway._run_a03_approved(now_epoch=105,approval_path=approval)
            self.assertFalse(Path(approval).exists())
            used=list((Path(atd)/'consumed').glob('used-*.json'))
            self.assertEqual(len(used),1)
            return r

    def test_sha_tamper_vetoes_after_consuming_permission(self):
        r=self._approved_run(tamper=True)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'EXECUTABLE_SHA256_MISMATCH')
        self.assertEqual(r['evidence']['validation_stage'],'PROCESS_PREFLIGHT')

    def test_authority_mismatch_vetoes_after_consuming_permission(self):
        r=self._approved_run(bad_authority=True)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'AUTHORITY_MISMATCH')
        self.assertEqual(r['evidence']['validation_stage'],'FROZEN_AUTHORITY')

if __name__=='__main__': unittest.main()
