from __future__ import annotations

import os
import sys
import threading
import unittest
import uuid
from unittest import mock

for path in ("/root/K/F/src","/root/K/K/src"):
    if path not in sys.path: sys.path.insert(0,path)

from kk_f import fk_gateway
from kk_k.fk_runtime import FKRuntimeError, execute_governed


def addr(tag): return "\0kk-fkruntime-"+tag+"-"+uuid.uuid4().hex[:10]

def server_once(a):
    ready=threading.Event(); errors=[]
    def target():
        try: fk_gateway.serve_once(address=a,allowed_uid=os.getuid(),ready=ready.set)
        except Exception as exc: errors.append(exc); ready.set()
    t=threading.Thread(target=target,daemon=True); t.start()
    if not ready.wait(2): raise AssertionError('gateway not ready')
    if errors: raise errors[0]
    return t,errors


class FKRuntimeTests(unittest.TestCase):
    def test_governed_a02_reaches_real_f_and_passes(self):
        a=addr('a02'); t,e=server_once(a)
        r=execute_governed('A02_READ_F_STATUS',[],address=a)
        t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(r['status'],'PASS')
        self.assertTrue(r['f_called'])
        self.assertEqual(r['receipt']['evidence'],{'kind':'F_STATUS','status':'ACCEPTED'})

    def test_governed_a05_reaches_real_f_and_passes(self):
        a=addr('a05'); t,e=server_once(a)
        r=execute_governed('A05_NO_ACTION',[],address=a)
        t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(r['status'],'PASS')
        self.assertTrue(r['f_called'])

    def test_a03_human_gate_reaches_f_for_f_owned_approval_check(self):
        a=addr('a03-human'); t,e=server_once(a)
        with mock.patch('kk_k.fk_runtime._audit_privileged_attempt') as audit:
            r=execute_governed('A03_RUN_F_SMOKE_TEST',[],address=a)
        audit.assert_called_once_with('A03_RUN_F_SMOKE_TEST','REQUIRE_HUMAN')
        t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(r['status'],'VETO')
        self.assertTrue(r['f_called'])
        self.assertEqual(r['action_id'],'A03_RUN_F_SMOKE_TEST')
        self.assertEqual(r['receipt']['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')
        self.assertEqual(r['receipt']['evidence']['validation_stage'],'HUMAN_APPROVAL')

    def test_consecutive_budget_stops_before_f(self):
        r=execute_governed('A02_READ_F_STATUS',['A02_READ_F_STATUS','A02_READ_F_STATUS'],address=addr('no-server'))
        self.assertEqual(r['status'],'STOP')
        self.assertFalse(r['f_called'])
        self.assertEqual(r['action_id'],'A05_NO_ACTION')

    def test_unknown_action_is_governance_error_not_transport(self):
        with self.assertRaises(FKRuntimeError):
            execute_governed('RUN_SHELL',[],address=addr('no-server'))


if __name__=='__main__': unittest.main()
