from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

for path in ("/root/K/F/src","/root/K/K/src"):
    if path not in sys.path: sys.path.insert(0,path)

from kk_f.fk_approval import FKApprovalError, issue_a03_approval, consume_a03_approval
from kk_f import fk_gateway
from kk_k.verifier import verify_receipt


class FKP01ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/root/K/FK/.test_tmp')
        self.path=str(Path(self.tmp.name)/'a03_approval.json')
    def tearDown(self):
        self.tmp.cleanup()

    def issue(self, now=100, ttl=10, nonce='a'*32):
        return issue_a03_approval(ttl_seconds=ttl,now_epoch=now,path=self.path,nonce=nonce)

    def test_issue_is_root_owned_0600_strict_a03(self):
        value=self.issue()
        st=os.stat(self.path)
        self.assertEqual(st.st_uid,0)
        self.assertEqual(st.st_mode & 0o777,0o600)
        self.assertEqual(value['action_id'],'A03_RUN_F_SMOKE_TEST')
        self.assertEqual(set(value),{'schema','action_id','nonce','issued_at','expires_at'})

    def test_nonroot_cannot_issue(self):
        with mock.patch('kk_f.fk_approval.os.geteuid',return_value=64160):
            with self.assertRaises(FKApprovalError): self.issue()
        self.assertFalse(Path(self.path).exists())

    def test_second_unconsumed_approval_cannot_overwrite_first(self):
        first=self.issue()
        with self.assertRaises(FKApprovalError): self.issue(nonce='b'*32)
        self.assertEqual(json.loads(Path(self.path).read_text())['nonce'],first['nonce'])

    def test_ttl_over_300_rejected(self):
        with self.assertRaises(FKApprovalError): self.issue(ttl=301)

    def test_missing_approval_is_typed_veto(self):
        r=fk_gateway._run_a03_approved(now_epoch=105,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')
        self.assertEqual(r['evidence']['validation_stage'],'HUMAN_APPROVAL')

    def test_valid_approval_allows_exactly_one_real_a03(self):
        self.issue()
        r=fk_gateway._run_a03_approved(now_epoch=105,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'PASS')
        self.assertFalse(Path(self.path).exists())
        used=list((Path(self.path).parent/'consumed').glob('used-*.json'))
        self.assertEqual(len(used),1)
        replay=fk_gateway._run_a03_approved(now_epoch=106,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',replay).result,'VETO')
        self.assertEqual(replay['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')

    def test_expired_approval_is_consumed_and_cannot_replay(self):
        self.issue(now=100,ttl=5)
        r=fk_gateway._run_a03_approved(now_epoch=106,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_EXPIRED')
        expired=list((Path(self.path).parent/'consumed').glob('expired-*.json'))
        self.assertEqual(len(expired),1)
        r2=fk_gateway._run_a03_approved(now_epoch=107,approval_path=self.path)
        self.assertEqual(r2['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')

    def test_world_writable_approval_is_invalid(self):
        self.issue(); os.chmod(self.path,0o666)
        r=fk_gateway._run_a03_approved(now_epoch=105,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_INVALID')

    def test_symlink_approval_is_invalid(self):
        real=Path(self.tmp.name)/'real.json'
        real.write_text('{}',encoding='utf-8'); real.chmod(0o600)
        Path(self.path).symlink_to(real)
        r=fk_gateway._run_a03_approved(now_epoch=105,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_INVALID')

    def test_malformed_approval_is_invalid(self):
        p=Path(self.path); p.write_text('{"schema":"FKP01.APPROVAL.1"}\n',encoding='utf-8'); p.chmod(0o600)
        r=fk_gateway._run_a03_approved(now_epoch=105,approval_path=self.path)
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_INVALID')

    def test_permission_consumed_before_execution_attempt(self):
        self.issue()
        with mock.patch('kk_f.fk_gateway._run_a03_static',side_effect=RuntimeError('simulated post-consume crash')):
            with self.assertRaises(RuntimeError):
                fk_gateway._run_a03_approved(now_epoch=105,approval_path=self.path)
        self.assertFalse(Path(self.path).exists())
        ok,reason,_=consume_a03_approval(now_epoch=106,path=self.path)
        self.assertFalse(ok); self.assertEqual(reason,'HUMAN_APPROVAL_REQUIRED')

    def test_fkp04_live_dispatch_is_human_gated_not_caller_approved(self):
        self.assertIn('A03_RUN_F_SMOKE_TEST',fk_gateway.ENABLED_ACTIONS)
        with mock.patch('kk_f.fk_gateway.consume_a03_approval', return_value=(False,'HUMAN_APPROVAL_REQUIRED',None)), \
             mock.patch('kk_f.fk_gateway._run_a03_static') as run_static:
            r=fk_gateway.dispatch('A03_RUN_F_SMOKE_TEST',peer_uid=123,allowed_uid=123)
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')
        self.assertEqual(r['evidence']['validation_stage'],'HUMAN_APPROVAL')
        run_static.assert_not_called()


if __name__=='__main__': unittest.main()
