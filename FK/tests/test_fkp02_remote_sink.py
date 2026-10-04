import json
import os
import threading
import time
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import initialize_state, load_canonical_events, load_state
from kk_k.audit_witness import remote_soul_audit_sink
from kk_k.soul_proposer import SoulProposer, SoulProposerError, SoulProviders


def role_json(role,action):
    if role=='a': return json.dumps({'schema':'KS01.SOUL_A.1','assessment':'a','confidence':'HIGH','candidate_actions':[action,'A05_NO_ACTION']})
    if role=='b': return json.dumps({'schema':'KS01.SOUL_B.1','assessment':'b','confidence':'HIGH','blocked_actions':[]})
    return json.dumps({'schema':'KS01.SOUL_C.1','assessment':'c','confidence':'HIGH','selected_action_id':action})

def evidence(action):
    return [{'schema':'KS02.EVIDENCE.1','evidence_id':'e1','source_id':'test','trust':'UNTRUSTED_EVIDENCE','freshness':'FRESH','stance':'SUPPORT','actions':[action],'claim':'support'}]


class FKP02RemoteSinkTests(unittest.TestCase):
    def setUp(self):
        self.state=Path('/root/K/F/evidence/fk')/('.remote-'+uuid4().hex+'.json')
        self.log=Path(str(self.state)+'.events.jsonl')
        initialize_state(str(self.state))
        self.address='\0fkp02-remote-'+uuid4().hex[:10]
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.thread=threading.Thread(target=fk_audit_gateway.serve_forever,kwargs={'address':self.address,'state_path':str(self.state),'log_path':str(self.log),'allowed_uid':os.getuid(),'stop_event':self.stop_event,'ready':self.ready.set},daemon=True)
        self.thread.start(); self.assertTrue(self.ready.wait(1.0))
    def tearDown(self):
        self.stop_event.set(); self.thread.join(timeout=1.0); self.assertFalse(self.thread.is_alive())
        self.state.unlink(missing_ok=True); self.log.unlink(missing_ok=True)
    def proposer(self,prefix):
        action='A02_READ_F_STATUS'
        return SoulProposer(
            providers=SoulProviders(soul_a=lambda _:role_json('a',action),soul_b=lambda _:role_json('b',action),soul_c=lambda _:role_json('c',action)),
            context_provider=lambda c:f'cycle={c}',evidence_provider=lambda _:evidence(action),
            audit_log_path=None,event_prefix=prefix,audit_sink=remote_soul_audit_sink(self.address),
        )
    def test_no_local_persistent_file_required_across_fresh_proposers(self):
        self.assertEqual(self.proposer('runA')(1),'A02_READ_F_STATUS')
        self.assertEqual(self.proposer('runB')(1),'A02_READ_F_STATUS')
        state=load_state(str(self.state)); events=load_canonical_events(str(self.log))
        self.assertEqual(state['generation'],2); self.assertEqual(len(events),2)
        self.assertEqual(events[-1]['prev_sha256'],events[-2]['entry_sha256'])
    def test_f_owns_canonical_log(self):
        self.proposer('runA')(1)
        st=self.log.stat(); self.assertEqual(st.st_uid,0); self.assertEqual(st.st_mode & 0o022,0)
    def test_remote_witness_unavailable_prevents_action_return(self):
        action='A02_READ_F_STATUS'
        p=SoulProposer(
            providers=SoulProviders(soul_a=lambda _:role_json('a',action),soul_b=lambda _:role_json('b',action),soul_c=lambda _:role_json('c',action)),
            context_provider=lambda c:'x',evidence_provider=lambda _:evidence(action),audit_log_path=None,event_prefix='missing',
            audit_sink=remote_soul_audit_sink('\0missing-fkp02-remote'),
        )
        with self.assertRaises(SoulProposerError): p(1)

if __name__=='__main__': unittest.main()
