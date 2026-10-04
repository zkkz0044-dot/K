import json
import os
import threading
import time
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import initialize_state, load_canonical_events
from kk_k.audit_witness import AuditWitnessError, append_remote_event, commit_belief_revision_event, query_current_beliefs
from kk_k.beliefs import BeliefError, build_revision


class FKP03BeliefLedgerTests(unittest.TestCase):
    def setUp(self):
        stem='.belief-'+uuid4().hex
        self.state=Path('/root/K/F/evidence/fk')/(stem+'.json')
        self.log=Path(str(self.state)+'.events.jsonl')
        initialize_state(str(self.state))
        self.address='\0belief-'+uuid4().hex[:14]
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.thread=threading.Thread(target=fk_audit_gateway.serve_forever,kwargs={'address':self.address,'state_path':str(self.state),'log_path':str(self.log),'allowed_uid':os.getuid(),'stop_event':self.stop_event,'ready':self.ready.set},daemon=True)
        self.thread.start(); self.assertTrue(self.ready.wait(1.0))
        append_remote_event(event_id='evidence-'+uuid4().hex[:8],kind='OBSERVATION',subject='test_evidence',summary='first evidence',address=self.address)

    def tearDown(self):
        self.stop_event.set(); self.thread.join(timeout=1.0); self.assertFalse(self.thread.is_alive())
        self.state.unlink(missing_ok=True); self.log.unlink(missing_ok=True)
        seg=Path(str(self.log)+'.segments')
        if seg.exists():
            for p in seg.iterdir(): p.unlink(missing_ok=True)
            seg.rmdir()

    def _commit(self,revision):
        commit_belief_revision_event(event_id=revision.state['revision_id'],summary=json.dumps(revision.state,sort_keys=True,separators=(',',':'),ensure_ascii=False),address=self.address)

    def test_create_query_update_preserves_prior_revision(self):
        first=build_revision(belief_id='world.sky',proposition='天空在白天通常看起来是蓝色。',status='TENTATIVE',confidence='LOW',evidence_sequences=[1],reason='初始观察',revision_id='belief-r1')
        self._commit(first)
        got=query_current_beliefs('天空 蓝色',limit=4,address=self.address)
        self.assertEqual(len(got),1); self.assertEqual(got[0]['revision'],1)
        append_remote_event(event_id='evidence-2',kind='OBSERVATION',subject='test_evidence',summary='second evidence',address=self.address)
        second=build_revision(belief_id='world.sky',proposition='在晴朗白天，天空通常呈蓝色。',status='SUPPORTED',confidence='MEDIUM',evidence_sequences=[1,3],reason='增加独立观察后提高置信度',previous=got[0],operation='UPDATE',revision_id='belief-r2')
        self._commit(second)
        got2=query_current_beliefs('晴朗 天空 蓝色',limit=4,address=self.address)
        self.assertEqual((got2[0]['revision'],got2[0]['status'],got2[0]['confidence']),(2,'SUPPORTED','MEDIUM'))
        revisions=[e for e in load_canonical_events(str(self.log)) if e.get('subject')=='belief_revision']
        self.assertEqual(len(revisions),2)
        self.assertIn('初始观察',revisions[0]['summary']); self.assertIn('增加独立观察',revisions[1]['summary'])

    def test_retraction_hides_current_belief_but_keeps_history(self):
        first=build_revision(belief_id='test.claim',proposition='一个待验证主张',status='TENTATIVE',confidence='LOW',evidence_sequences=[1],reason='初始',revision_id='belief-a1')
        self._commit(first); current=query_current_beliefs('待验证主张',address=self.address)[0]
        append_remote_event(event_id='evidence-x',kind='OBSERVATION',subject='test_evidence',summary='counter evidence',address=self.address)
        retracted=build_revision(belief_id='test.claim',proposition='一个待验证主张',status='RETRACTED',confidence='LOW',evidence_sequences=[3],reason='反证使当前主张撤回',previous=current,operation='RETRACT',revision_id='belief-a2')
        self._commit(retracted)
        self.assertEqual(query_current_beliefs('待验证主张',address=self.address),())
        history=[e for e in load_canonical_events(str(self.log)) if e.get('subject')=='belief_revision']
        self.assertEqual(len(history),2)

    def test_forged_predecessor_hash_is_rejected(self):
        first=build_revision(belief_id='claim.hash',proposition='初始主张',status='TENTATIVE',confidence='LOW',evidence_sequences=[1],reason='初始',revision_id='belief-h1')
        self._commit(first); current=dict(query_current_beliefs('初始主张',address=self.address)[0]); current['revision_sha256']='f'*64
        bad=build_revision(belief_id='claim.hash',proposition='修改主张',status='SUPPORTED',confidence='MEDIUM',evidence_sequences=[1],reason='伪造前驱',previous=current,operation='UPDATE',revision_id='belief-h2')
        with self.assertRaises(AuditWitnessError): self._commit(bad)

    def test_ordinary_commit_cannot_bypass_belief_gate(self):
        from kk_k.audit_witness import _build_event_from_head, _parse_receipt, _request, query_witness
        head=query_witness(address=self.address)
        revision=build_revision(belief_id='claim.bypass',proposition='不可绕过',status='TENTATIVE',confidence='LOW',evidence_sequences=[1],reason='测试',revision_id='belief-b1')
        event=_build_event_from_head(head,event_id='belief-b1',kind='SYSTEM',subject='belief_revision',summary=json.dumps(revision.state,sort_keys=True,separators=(',',':'),ensure_ascii=False))
        with self.assertRaisesRegex(AuditWitnessError,'COGNITIVE_COMMIT_REQUIRED'):
            _parse_receipt(_request({'schema':'FK_AUDIT.COMMIT.2','event':event},self.address))

    def test_belief_revision_requires_prior_evidence(self):
        with self.assertRaises(BeliefError):
            build_revision(belief_id='claim.none',proposition='无证据主张',status='TENTATIVE',confidence='LOW',evidence_sequences=[],reason='无证据')


if __name__=='__main__': unittest.main()
