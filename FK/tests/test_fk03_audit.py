from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import threading
import unittest
import uuid

for path in ("/root/K/F/src", "/root/K/K/src"):
    if path not in sys.path:
        sys.path.insert(0, path)

from kk_f import fk_gateway
from kk_k.boundary import submit_action
from kk_k.fk_client import submit as fk_submit
from kk_k.verifier import verify_receipt


def addr(tag): return "\0kk-fk03-"+tag+"-"+uuid.uuid4().hex[:10]

def server_once(a):
    ready=threading.Event(); errors=[]
    def target():
        try: fk_gateway.serve_once(address=a,allowed_uid=os.getuid(),ready=ready.set)
        except Exception as exc: errors.append(exc); ready.set()
    t=threading.Thread(target=target,daemon=True); t.start()
    if not ready.wait(2): raise AssertionError('gateway not ready')
    if errors: raise errors[0]
    return t,errors

def children():
    p=Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
    return p.read_text().strip() if p.exists() else ''

def raw_roundtrip(a, raw):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(2)
    try:
        s.connect(a); s.sendall(raw); data=bytearray()
        while not data.endswith(b'\n'):
            c=s.recv(4096)
            if not c: break
            data.extend(c)
        return json.loads(bytes(data).decode())
    finally: s.close()


class FK03AuditTests(unittest.TestCase):
    def test_a04_real_append_exact_one_and_verifier(self):
        log=Path('/root/K/F/evidence/fk/decision_markers.jsonl')
        before=log.read_text(encoding='utf-8').splitlines()
        child_before=children()
        a=addr('one'); t,e=server_once(a)
        r=submit_action('A04_WRITE_K_DECISION_LOG',lambda aid:fk_submit(aid,address=a))
        t.join(2); child_after=children()
        after=log.read_text(encoding='utf-8').splitlines()
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt('A04_WRITE_K_DECISION_LOG',r).result,'PASS')
        self.assertEqual(len(after),len(before)+1)
        self.assertEqual(json.loads(after[-1]),{
            'schema':'FK03.A04.1','action_id':'A04_WRITE_K_DECISION_LOG','marker':'K_DECISION_ACCEPTED'})
        self.assertEqual(child_before,child_after)

    def test_a04_two_calls_append_two_records(self):
        log=Path('/root/K/F/evidence/fk/decision_markers.jsonl'); before=len(log.read_text().splitlines())
        for tag in ('a','b'):
            a=addr(tag); t,e=server_once(a); r=fk_submit('A04_WRITE_K_DECISION_LOG',address=a); t.join(2)
            self.assertEqual(e,[]); self.assertEqual(verify_receipt('A04_WRITE_K_DECISION_LOG',r).result,'PASS')
        self.assertEqual(len(log.read_text().splitlines()),before+2)

    def test_production_audit_file_is_root_owned_and_nonwritable_by_others(self):
        st=os.stat('/root/K/F/evidence/fk/decision_markers.jsonl')
        self.assertEqual(st.st_uid,0)
        self.assertFalse(st.st_mode & (stat.S_IWGRP|stat.S_IWOTH))

    def test_world_writable_audit_file_is_vetoed(self):
        original=fk_gateway.AUDIT_LOG_PATH
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            p=Path(td)/'audit.jsonl'; p.write_text('',encoding='utf-8'); p.chmod(0o666)
            fk_gateway.AUDIT_LOG_PATH=str(p)
            try:
                a=addr('mode'); t,e=server_once(a); r=fk_submit('A04_WRITE_K_DECISION_LOG',address=a); t.join(2)
            finally: fk_gateway.AUDIT_LOG_PATH=original
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt('A04_WRITE_K_DECISION_LOG',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'AUDIT_LOG_INVALID')
        self.assertEqual(r['evidence']['validation_stage'],'F_AUDIT')

    def test_symlink_audit_file_is_vetoed(self):
        original=fk_gateway.AUDIT_LOG_PATH
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            root=Path(td); real=root/'real.jsonl'; link=root/'link.jsonl'; real.write_text('',encoding='utf-8'); real.chmod(0o600); link.symlink_to(real)
            fk_gateway.AUDIT_LOG_PATH=str(link)
            try:
                a=addr('link'); t,e=server_once(a); r=fk_submit('A04_WRITE_K_DECISION_LOG',address=a); t.join(2)
            finally: fk_gateway.AUDIT_LOG_PATH=original
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt('A04_WRITE_K_DECISION_LOG',r).result,'VETO')
        self.assertEqual(r['evidence']['reason_code'],'AUDIT_LOG_INVALID')

    def test_caller_cannot_inject_log_text_or_path(self):
        a=addr('inject'); t,e=server_once(a)
        raw=b'{"schema":"FK01.REQUEST.1","action_id":"A04_WRITE_K_DECISION_LOG","text":"evil","path":"/tmp/x"}\n'
        response=raw_roundtrip(a,raw); t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(response,{'schema':'FK01.ERROR.1','reason_code':'INVALID_REQUEST','stage':'REQUEST_PARSE'})


if __name__=='__main__': unittest.main()
