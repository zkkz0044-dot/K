from __future__ import annotations
import inspect, os, sys, threading, unittest, uuid
from unittest import mock
for p in ('/root/K/F/src','/root/K/K/src'):
    if p not in sys.path: sys.path.insert(0,p)
from kk_f import fk_gateway
from kk_k import fk_runtime
from kk_k.fk_client import submit
from kk_k.governance import GovernanceDecision
from kk_k.verifier import verify_receipt

def addr(): return '\0fkp04-'+uuid.uuid4().hex[:12]

def serve_once(a):
    ready=threading.Event(); errors=[]
    def target():
        try: fk_gateway.serve_once(address=a,allowed_uid=os.getuid(),ready=ready.set)
        except Exception as exc: errors.append(exc); ready.set()
    t=threading.Thread(target=target,daemon=True); t.start()
    if not ready.wait(2): raise AssertionError('server not ready')
    if errors: raise errors[0]
    return t,errors

class FKP04ProductionA03Tests(unittest.TestCase):
    def test_a03_is_in_live_enabled_set(self):
        self.assertIn('A03_RUN_F_SMOKE_TEST',fk_gateway.ENABLED_ACTIONS)

    def test_request_schema_still_has_no_approval_fields(self):
        self.assertEqual(fk_gateway.REQUEST_KEYS,frozenset({'schema','action_id'}))
        self.assertNotIn('approval',inspect.signature(fk_runtime.execute_governed).parameters)
        self.assertNotIn('human_approved',inspect.signature(fk_runtime.execute_governed).parameters)

    def test_missing_approval_starts_no_process(self):
        with mock.patch('kk_f.fk_gateway.consume_a03_approval',return_value=(False,'HUMAN_APPROVAL_REQUIRED',None)), \
             mock.patch('kk_f.fk_gateway._run_a03_static') as run_static:
            r=fk_gateway.dispatch('A03_RUN_F_SMOKE_TEST',peer_uid=1,allowed_uid=1)
        run_static.assert_not_called()
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'VETO')

    def test_valid_f_owned_approval_enters_static_chain_once(self):
        receipt={'schema':'FK01.F_RECEIPT.1','action_id':'A03_RUN_F_SMOKE_TEST','outcome':'EXECUTED','evidence':{'kind':'F_SMOKE','exit_code':0,'tests_failed':0}}
        with mock.patch('kk_f.fk_gateway.consume_a03_approval',return_value=(True,'HUMAN_APPROVAL_ACCEPTED',{'nonce':'a'*32})), \
             mock.patch('kk_f.fk_gateway._run_a03_static',return_value=receipt) as run_static:
            r=fk_gateway.dispatch('A03_RUN_F_SMOKE_TEST',peer_uid=1,allowed_uid=1)
        run_static.assert_called_once_with()
        self.assertEqual(verify_receipt('A03_RUN_F_SMOKE_TEST',r).result,'PASS')

    def test_k_require_human_routes_only_fixed_a03_to_f(self):
        receipt={'schema':'FK01.F_RECEIPT.1','action_id':'A03_RUN_F_SMOKE_TEST','outcome':'VETO','evidence':{'kind':'VETO','reason_code':'HUMAN_APPROVAL_REQUIRED','validation_stage':'HUMAN_APPROVAL'}}
        with mock.patch('kk_k.fk_runtime.load_policy',return_value={}), \
             mock.patch('kk_k.fk_runtime.govern',return_value=GovernanceDecision('REQUIRE_HUMAN','A03_RUN_F_SMOKE_TEST','HUMAN_APPROVAL_REQUIRED')), \
             mock.patch('kk_k.fk_runtime._audit_privileged_attempt') as audit, \
             mock.patch('kk_k.fk_runtime.submit',return_value=receipt) as sub:
            out=fk_runtime.execute_governed('A03_RUN_F_SMOKE_TEST',[])
        audit.assert_called_once_with('A03_RUN_F_SMOKE_TEST','REQUIRE_HUMAN')
        sub.assert_called_once()
        self.assertTrue(out['f_called']); self.assertEqual(out['status'],'VETO')

    def test_other_require_human_action_does_not_get_generic_forwarding(self):
        with mock.patch('kk_k.fk_runtime.load_policy',return_value={}), \
             mock.patch('kk_k.fk_runtime.govern',return_value=GovernanceDecision('REQUIRE_HUMAN','A04_WRITE_K_DECISION_LOG','HUMAN_APPROVAL_REQUIRED')), \
             mock.patch('kk_k.fk_runtime.submit') as sub:
            out=fk_runtime.execute_governed('A04_WRITE_K_DECISION_LOG',[])
        sub.assert_not_called()
        self.assertFalse(out['f_called']); self.assertEqual(out['status'],'REQUIRE_HUMAN')

    def test_real_network_missing_approval_returns_typed_veto(self):
        a=addr()
        with mock.patch('kk_f.fk_gateway.consume_a03_approval',return_value=(False,'HUMAN_APPROVAL_REQUIRED',None)):
            t,e=serve_once(a); r=submit('A03_RUN_F_SMOKE_TEST',address=a); t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(r['evidence']['reason_code'],'HUMAN_APPROVAL_REQUIRED')
        self.assertEqual(r['evidence']['validation_stage'],'HUMAN_APPROVAL')

    def test_peer_auth_still_precedes_human_gate(self):
        with mock.patch('kk_f.fk_gateway.consume_a03_approval') as consume:
            r=fk_gateway.dispatch('A03_RUN_F_SMOKE_TEST',peer_uid=2,allowed_uid=1)
        consume.assert_not_called()
        self.assertEqual(r['evidence']['reason_code'],'PEER_AUTH_DENY')

if __name__=='__main__': unittest.main()
