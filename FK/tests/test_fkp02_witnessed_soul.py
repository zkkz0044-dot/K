import json
import os
import threading
import time
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import initialize_state
from kk_k.audit_witness import compare_with_witness
from kk_k.soul_proposer import SoulProposer, SoulProviders
from kk_k.test_support import project_tempdir
from kk_k.witnessed_soul_proposer import WitnessedSoulProposer, WitnessedSoulProposerError


def soul_json(role, action):
    if role=='a': return json.dumps({'schema':'KS01.SOUL_A.1','assessment':'a','confidence':'HIGH','candidate_actions':[action,'A05_NO_ACTION']})
    if role=='b': return json.dumps({'schema':'KS01.SOUL_B.1','assessment':'b','confidence':'HIGH','blocked_actions':[]})
    return json.dumps({'schema':'KS01.SOUL_C.1','assessment':'c','confidence':'HIGH','selected_action_id':action})

def evidence(action):
    return [{'schema':'KS02.EVIDENCE.1','evidence_id':'e1','source_id':'test','trust':'UNTRUSTED_EVIDENCE','freshness':'FRESH','stance':'SUPPORT','actions':[action],'claim':'support'}]


class FKP02WitnessedSoulTests(unittest.TestCase):
    def setUp(self):
        self.tmp=project_tempdir(); self.root=Path(self.tmp.name); self.audit=self.root/'soul.jsonl'
        self.state=Path('/root/K/F/evidence/fk')/('.soul-'+uuid4().hex+'.json'); initialize_state(str(self.state))
        self.address='\0fkp02-soul-'+uuid4().hex[:10]
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.thread=threading.Thread(target=fk_audit_gateway.serve_forever,kwargs={'address':self.address,'state_path':str(self.state),'allowed_uid':os.getuid(),'stop_event':self.stop_event,'ready':self.ready.set},daemon=True)
        self.thread.start(); self.assertTrue(self.ready.wait(1.0))
    def tearDown(self):
        self.stop_event.set(); self.thread.join(timeout=1.0); self.assertFalse(self.thread.is_alive())
        self.tmp.cleanup(); self.state.unlink(missing_ok=True)
    def base(self):
        action='A02_READ_F_STATUS'
        return SoulProposer(
            providers=SoulProviders(soul_a=lambda _:soul_json('a',action),soul_b=lambda _:soul_json('b',action),soul_c=lambda _:soul_json('c',action)),
            context_provider=lambda c:f'cycle={c}', evidence_provider=lambda _:evidence(action),
            audit_log_path=str(self.audit), event_prefix='witnessed',
        )
    def test_soul_action_not_returned_until_witness_match(self):
        w=WitnessedSoulProposer(proposer=self.base(),audit_log_path=str(self.audit),witness_address=self.address)
        self.assertEqual(w(1),'A02_READ_F_STATUS')
        self.assertEqual(compare_with_witness(str(self.audit),address=self.address),'MATCH')
    def test_witness_unavailable_fails_before_action_return(self):
        w=WitnessedSoulProposer(proposer=self.base(),audit_log_path=str(self.audit),witness_address='\0definitely-missing-fkp02')
        with self.assertRaises(WitnessedSoulProposerError): w(1)
    def test_rollback_prevents_next_soul_action(self):
        w=WitnessedSoulProposer(proposer=self.base(),audit_log_path=str(self.audit),witness_address=self.address)
        self.assertEqual(w(1),'A02_READ_F_STATUS')
        self.audit.write_bytes(b'')
        with self.assertRaises(WitnessedSoulProposerError): w(2)

if __name__=='__main__': unittest.main()
