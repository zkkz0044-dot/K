from __future__ import annotations
import json, re, sys, unittest
from unittest import mock
for p in ('/root/K/F/src','/root/K/K/src'):
    if p not in sys.path: sys.path.insert(0,p)
from kk_k import fk_runtime
from kk_k.audit_witness import AuditWitnessError
from kk_k.governance import GovernanceDecision

A03='A03_RUN_F_SMOKE_TEST'
VETO={'schema':'FK01.F_RECEIPT.1','action_id':A03,'outcome':'VETO','evidence':{'kind':'VETO','reason_code':'HUMAN_APPROVAL_REQUIRED','validation_stage':'HUMAN_APPROVAL'}}

class FKP05PrivilegedAuditTests(unittest.TestCase):
    def test_privileged_audit_is_fixed_bounded_event(self):
        with mock.patch('kk_k.fk_runtime.append_remote_event') as append:
            fk_runtime._audit_privileged_attempt(A03,'REQUIRE_HUMAN')
        kw=append.call_args.kwargs
        self.assertRegex(kw['event_id'],r'^privileged-[0-9a-f]{16}$')
        self.assertEqual(kw['kind'],'EXECUTION')
        self.assertEqual(kw['subject'],'privileged_attempt')
        self.assertEqual(json.loads(kw['summary']),{'action_id':A03,'governance':'REQUIRE_HUMAN'})

    def test_audit_failure_stops_before_f(self):
        with mock.patch('kk_k.fk_runtime.load_policy',return_value={}), \
             mock.patch('kk_k.fk_runtime.govern',return_value=GovernanceDecision('REQUIRE_HUMAN',A03,'HUMAN_APPROVAL_REQUIRED')), \
             mock.patch('kk_k.fk_runtime._audit_privileged_attempt',side_effect=AuditWitnessError('down')), \
             mock.patch('kk_k.fk_runtime.submit') as submit:
            with self.assertRaises(fk_runtime.FKRuntimeError): fk_runtime.execute_governed(A03,[])
        submit.assert_not_called()

    def test_human_gated_action_cannot_become_plain_allow(self):
        with mock.patch('kk_k.fk_runtime.load_policy',return_value={}), \
             mock.patch('kk_k.fk_runtime.govern',return_value=GovernanceDecision('ALLOW',A03,'POLICY_ALLOW')), \
             mock.patch('kk_k.fk_runtime.submit') as submit:
            with self.assertRaises(fk_runtime.FKRuntimeError): fk_runtime.execute_governed(A03,[])
        submit.assert_not_called()

    def test_audit_precedes_f_submit(self):
        order=[]
        with mock.patch('kk_k.fk_runtime.load_policy',return_value={}), \
             mock.patch('kk_k.fk_runtime.govern',return_value=GovernanceDecision('REQUIRE_HUMAN',A03,'HUMAN_APPROVAL_REQUIRED')), \
             mock.patch('kk_k.fk_runtime._audit_privileged_attempt',side_effect=lambda *a: order.append('audit')), \
             mock.patch('kk_k.fk_runtime.submit',side_effect=lambda *a,**k: order.append('submit') or VETO):
            out=fk_runtime.execute_governed(A03,[])
        self.assertEqual(order,['audit','submit'])
        self.assertEqual(out['status'],'VETO')

if __name__=='__main__': unittest.main()
