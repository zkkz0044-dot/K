from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

for path in ("/root/K/F/src","/root/K/K/src"):
    if path not in sys.path: sys.path.insert(0,path)

from kk_f import fk_gateway
from kk_k.fk_client import submit as fk_submit
from kk_k.verifier import verify_receipt


def addr(tag): return "\0kk-fk04-"+tag+"-"+uuid.uuid4().hex[:10]

def server_once(a):
    ready=threading.Event(); errors=[]
    def target():
        try: fk_gateway.serve_once(address=a,allowed_uid=os.getuid(),ready=ready.set)
        except Exception as exc: errors.append(exc); ready.set()
    t=threading.Thread(target=target,daemon=True); t.start()
    if not ready.wait(2): raise AssertionError('gateway not ready')
    if errors: raise errors[0]
    return t,errors


def build_fixture(root: Path, *, tamper_after=False, authority_mode=0o600):
    script=root/'smoke.py'
    script.write_text('#!/usr/bin/python3\nraise SystemExit(0)\n',encoding='utf-8'); script.chmod(0o755)
    digest=hashlib.sha256(script.read_bytes()).hexdigest()
    spec={"version":"0.1","executable":str(script),"argv":[],"cwd":"/root/K/F","env":{},"sha256":digest}
    manifest=root/'authority.json'
    manifest.write_text(json.dumps({"version":"0.2","authority_id":"fk-a03-smoke","process_spec":spec,"max_restart_attempts":1},sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    manifest.chmod(authority_mode)
    if tamper_after: script.write_text('#!/usr/bin/python3\nraise SystemExit(9)\n',encoding='utf-8'); script.chmod(0o755)
    return script,manifest


class FK04StaticA03Tests(unittest.TestCase):
    def test_real_static_a03_traverses_f_chain_and_k_verifies(self):
        r=fk_gateway._run_a03_static()
        self.assertEqual(r['schema'],'FK01.F_RECEIPT.1')
        self.assertEqual(r['action_id'],'A03_RUN_F_SMOKE_TEST')
        self.assertEqual(r['outcome'],'EXECUTED')
        self.assertEqual(r['evidence'],{'kind':'F_SMOKE','exit_code':0,'tests_failed':0})
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'PASS')

    def test_static_runner_accepts_no_caller_parameters(self):
        self.assertEqual(list(inspect.signature(fk_gateway._run_a03_static).parameters),[])
        self.assertEqual(fk_gateway.A03_AUTHORITY_PATH,'/root/K/F/fk_actions/a03_authority.json')
        self.assertEqual(fk_gateway.A03_EXPECTED_EXECUTABLE,'/root/K/F/fk_actions/a03_smoke.py')

    def test_sha_tamper_returns_specific_typed_veto(self):
        old_auth=fk_gateway.A03_AUTHORITY_PATH; old_exe=fk_gateway.A03_EXPECTED_EXECUTABLE
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            script,manifest=build_fixture(Path(td),tamper_after=True)
            fk_gateway.A03_AUTHORITY_PATH=str(manifest); fk_gateway.A03_EXPECTED_EXECUTABLE=str(script)
            try: r=fk_gateway._run_a03_static()
            finally: fk_gateway.A03_AUTHORITY_PATH=old_auth; fk_gateway.A03_EXPECTED_EXECUTABLE=old_exe
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'EXECUTABLE_SHA256_MISMATCH')
        self.assertEqual(r['evidence']['validation_stage'],'PROCESS_PREFLIGHT')

    def test_world_writable_authority_is_vetoed(self):
        old_auth=fk_gateway.A03_AUTHORITY_PATH; old_exe=fk_gateway.A03_EXPECTED_EXECUTABLE
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            script,manifest=build_fixture(Path(td),authority_mode=0o666)
            fk_gateway.A03_AUTHORITY_PATH=str(manifest); fk_gateway.A03_EXPECTED_EXECUTABLE=str(script)
            try: r=fk_gateway._run_a03_static()
            finally: fk_gateway.A03_AUTHORITY_PATH=old_auth; fk_gateway.A03_EXPECTED_EXECUTABLE=old_exe
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'AUTHORITY_MISMATCH')
        self.assertEqual(r['evidence']['validation_stage'],'FROZEN_AUTHORITY')

    def test_mapping_mismatch_is_vetoed_before_execution(self):
        old_auth=fk_gateway.A03_AUTHORITY_PATH; old_exe=fk_gateway.A03_EXPECTED_EXECUTABLE
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            script,manifest=build_fixture(Path(td))
            fk_gateway.A03_AUTHORITY_PATH=str(manifest); fk_gateway.A03_EXPECTED_EXECUTABLE='/root/K/F/not-the-candidate'
            try: r=fk_gateway._run_a03_static()
            finally: fk_gateway.A03_AUTHORITY_PATH=old_auth; fk_gateway.A03_EXPECTED_EXECUTABLE=old_exe
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'AUTHORITY_MISMATCH')

    def test_a03_network_reaches_f_but_missing_approval_vetoes(self):
        self.assertIn('A03_RUN_F_SMOKE_TEST',fk_gateway.ENABLED_ACTIONS)
        a=addr('human-gated')
        from unittest import mock
        with mock.patch('kk_f.fk_gateway.consume_a03_approval', return_value=(False,'HUMAN_APPROVAL_REQUIRED',None)):
            t,e=server_once(a); r=fk_submit('A03_RUN_F_SMOKE_TEST',address=a); t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')
        self.assertEqual(r['evidence']['validation_stage'],'HUMAN_APPROVAL')


if __name__=='__main__': unittest.main()
