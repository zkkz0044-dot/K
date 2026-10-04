import copy
import json
import os
import threading
import time
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import commit_event, initialize_state
from kk_k.audit_witness import AuditWitnessError, append_remote_event, commit_personality_revision_event, query_personality_state
from kk_k.memory import append_event
from kk_k.personality import PersonalityError, build_personality_revision, load_personality_core, load_personality_snapshot
from kk_k.test_support import project_tempdir


class FKP03PersonalityStateTests(unittest.TestCase):
    def setUp(self):
        self.state=Path('/root/K/F/evidence/fk')/('.personality-'+uuid4().hex+'.json')
        self.log=Path(str(self.state)+'.events.jsonl')
        initialize_state(str(self.state))
        self.tmp=project_tempdir(); self.local=Path(self.tmp.name)/'seed.jsonl'
        for i in range(1,4):
            e=append_event(str(self.local),event_id=f'seed{i}',kind='SYSTEM',subject='audit',summary=f'seed-{i}')
            commit_event(str(self.state),e,canonical_log_path=str(self.log))
        self.core=load_personality_core()
        self.address='\0personality-'+uuid4().hex[:12]
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.thread=threading.Thread(target=fk_audit_gateway.serve_forever,kwargs={'address':self.address,'state_path':str(self.state),'log_path':str(self.log),'allowed_uid':os.getuid(),'stop_event':self.stop_event,'ready':self.ready.set},daemon=True)
        self.thread.start(); self.assertTrue(self.ready.wait(1.0))
    def tearDown(self):
        self.stop_event.set(); self.thread.join(timeout=1.0); self.assertFalse(self.thread.is_alive())
        self.tmp.cleanup(); self.state.unlink(missing_ok=True); self.log.unlink(missing_ok=True)

    def test_no_revision_returns_trusted_core(self):
        r=query_personality_state(self.core.state,self.core.sha256,address=self.address)
        self.assertEqual(r['state'],self.core.state); self.assertEqual(r['revision_count'],0)

    def _first_summary(self):
        snap=load_personality_snapshot(address=self.address)
        return snap,build_personality_revision(snap,trait='curiosity',value='HIGH_CURIOSITY',confidence='MEDIUM',evidence_sequences=[1,2,3],reason='three durable observations support a first tentative trait')[1]

    def test_valid_revision_round_trip(self):
        snap,summary=self._first_summary()
        commit_personality_revision_event(self.core.state,self.core.sha256,event_id='pr1',summary=summary,address=self.address)
        got=load_personality_snapshot(address=self.address)
        self.assertEqual(got.revision_count,1); self.assertEqual(got.state['version'],snap.state['version']+1)
        self.assertEqual(got.state['traits']['curiosity']['value'],'HIGH_CURIOSITY')

    def test_generic_commit_cannot_bypass_personality_gate(self):
        _snap,summary=self._first_summary()
        with self.assertRaisesRegex(AuditWitnessError,'COGNITIVE_COMMIT_REQUIRED'):
            append_remote_event(event_id='bypass',kind='SYSTEM',subject='personality_revision',summary=summary,address=self.address)
        self.assertEqual(load_personality_snapshot(address=self.address).revision_count,0)

    def test_too_fast_second_revision_is_rejected_without_poisoning_state(self):
        snap,summary=self._first_summary()
        commit_personality_revision_event(self.core.state,self.core.sha256,event_id='pr1',summary=summary,address=self.address)
        one=load_personality_snapshot(address=self.address)
        _state,summary2=build_personality_revision(one,trait='warmth',value='MEASURED_WARMTH',confidence='MEDIUM',evidence_sequences=[1,2,3],reason='candidate warmth evidence')
        with self.assertRaisesRegex(AuditWitnessError,'COGNITIVE_STATE_INVALID'):
            commit_personality_revision_event(self.core.state,self.core.sha256,event_id='pr2',summary=summary2,address=self.address)
        self.assertEqual(load_personality_snapshot(address=self.address).revision_count,1)

    def test_forged_multi_trait_jump_is_rejected(self):
        snap,summary=self._first_summary(); d=json.loads(summary)
        d['state']['traits']['warmth']['value']='FORGED_WARMTH'
        forged=json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        with self.assertRaisesRegex(AuditWitnessError,'COGNITIVE_STATE_INVALID'):
            commit_personality_revision_event(self.core.state,self.core.sha256,event_id='forged',summary=forged,address=self.address)
        self.assertEqual(load_personality_snapshot(address=self.address).revision_count,0)

    def test_revision_requires_multiple_evidence_events(self):
        snap=load_personality_snapshot(address=self.address)
        with self.assertRaises(PersonalityError):
            build_personality_revision(snap,trait='curiosity',value='X',confidence='LOW',evidence_sequences=[1,2],reason='too little evidence')

if __name__=='__main__': unittest.main()
