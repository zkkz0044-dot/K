import json
import os
import socket
import threading
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import commit_event, initialize_state, load_state
from kk_k.governance import load_policy
from kk_k.loop import run_bounded_loop
from kk_k.soul_proposer import SoulProposer, SoulProviders
from kk_k.test_support import project_tempdir
from kk_k.memory import append_event
from kk_k.witnessed_soul_proposer import WitnessedSoulProposer


def role_json(role,action):
    if role=='a':
        return json.dumps({'schema':'KS01.SOUL_A.1','assessment':'a','confidence':'HIGH','candidate_actions':[action,'A05_NO_ACTION'] if action!='A05_NO_ACTION' else [action]})
    if role=='b':
        return json.dumps({'schema':'KS01.SOUL_B.1','assessment':'b','confidence':'HIGH','blocked_actions':[]})
    return json.dumps({'schema':'KS01.SOUL_C.1','assessment':'c','confidence':'HIGH','selected_action_id':action})


def evidence(action):
    return [{'schema':'KS02.EVIDENCE.1','evidence_id':'e1','source_id':'test','trust':'UNTRUSTED_EVIDENCE','freshness':'FRESH','stance':'SUPPORT','actions':[action],'claim':'x'}]


class FKWitnessedSoulTests(unittest.TestCase):
    def setUp(self):
        self.tmp=project_tempdir(); self.root=Path(self.tmp.name)
        self.audit=str(self.root/'soul-audit.jsonl')
        self.state=Path('/root/K/F/evidence/fk')/('.test-soul-witness-'+uuid4().hex+'.json')
        initialize_state(str(self.state))
        self.policy=load_policy('/root/K/K/K06_POLICY.json')

    def tearDown(self):
        self.tmp.cleanup()
        try: self.state.unlink()
        except FileNotFoundError: pass

    def base(self,action):
        return SoulProposer(
            providers=SoulProviders(
                soul_a=lambda _:role_json('a',action),
                soul_b=lambda _:role_json('b',action),
                soul_c=lambda _:role_json('c',action),
            ),
            context_provider=lambda cycle:f'cycle={cycle}',
            evidence_provider=lambda _:evidence(action),
            audit_log_path=self.audit,event_prefix='wit',
        )

    def server_n(self,count):
        address='\0fk-wit-'+uuid4().hex[:12]
        ready=threading.Event(); errors=[]
        def server():
            sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            try:
                sock.bind(address); sock.listen(8); ready.set()
                for _ in range(count):
                    conn,_=sock.accept()
                    with conn:
                        fk_audit_gateway.handle_connection(conn,state_path=str(self.state),allowed_uid=os.getuid())
            except Exception as exc:
                errors.append(exc)
            finally:
                sock.close()
        thread=threading.Thread(target=server,daemon=True)
        thread.start(); self.assertTrue(ready.wait(2))
        return address,thread,errors

    def finish(self,thread,errors):
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[])

    def test_witnessed_safe_action_reaches_k08_executor(self):
        address,thread,errors=self.server_n(3)
        proposer=WitnessedSoulProposer(proposer=self.base('A02_READ_F_STATUS'),audit_log_path=self.audit,witness_address=address)
        seen=[]
        r=run_bounded_loop(policy=self.policy,proposer=proposer,executor=lambda a:seen.append(a) or {'action_id':a,'mechanical_verdict':'PASS'},log_path=str(self.root/'loop.jsonl'),max_cycles=1)
        self.finish(thread,errors)
        self.assertEqual((r['status'],seen),('MAX_CYCLES',['A02_READ_F_STATUS']))
        self.assertEqual(load_state(str(self.state))['generation'],1)

    def test_a03_is_witnessed_then_human_gate_blocks_executor(self):
        address,thread,errors=self.server_n(3)
        proposer=WitnessedSoulProposer(proposer=self.base('A03_RUN_F_SMOKE_TEST'),audit_log_path=self.audit,witness_address=address)
        seen=[]
        r=run_bounded_loop(policy=self.policy,proposer=proposer,executor=lambda a:seen.append(a) or {'action_id':a,'mechanical_verdict':'PASS'},log_path=str(self.root/'loop.jsonl'),max_cycles=8)
        self.finish(thread,errors)
        self.assertEqual(r['status'],'REQUIRE_HUMAN')
        self.assertEqual(seen,[])
        self.assertEqual(load_state(str(self.state))['generation'],1)

    def test_witness_mismatch_becomes_proposer_error_no_executor(self):
        other=Path(self.tmp.name)/'other.jsonl'
        event=append_event(str(other),event_id='other-1',kind='SYSTEM',subject='audit',summary='other')
        commit_event(str(self.state),event,canonical_log_path=str(self.state)+'.events.jsonl')
        address,thread,errors=self.server_n(1)
        proposer=WitnessedSoulProposer(proposer=self.base('A02_READ_F_STATUS'),audit_log_path=self.audit,witness_address=address)
        seen=[]
        r=run_bounded_loop(policy=self.policy,proposer=proposer,executor=lambda a:seen.append(a),log_path=str(self.root/'loop.jsonl'),max_cycles=8)
        self.finish(thread,errors)
        self.assertEqual(r['status'],'PROPOSER_ERROR')
        self.assertEqual(seen,[])

    def test_witness_unavailable_stops_before_executor(self):
        address='\0missing-'+uuid4().hex[:12]
        proposer=WitnessedSoulProposer(proposer=self.base('A02_READ_F_STATUS'),audit_log_path=self.audit,witness_address=address)
        seen=[]
        r=run_bounded_loop(policy=self.policy,proposer=proposer,executor=lambda a:seen.append(a),log_path=str(self.root/'loop.jsonl'),max_cycles=8)
        self.assertEqual(r['status'],'PROPOSER_ERROR')
        self.assertEqual(seen,[])


if __name__=='__main__':
    unittest.main()
