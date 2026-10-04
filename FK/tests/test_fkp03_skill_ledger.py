import hashlib
import json
import os
import threading
import time
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import initialize_state, load_canonical_events
from kk_k.audit_witness import AuditWitnessError, append_remote_event, commit_skill_revision_event, query_current_skills
from kk_k.skills import build_revision

class FKP03SkillLedgerTests(unittest.TestCase):
    def setUp(self):
        stem='.skill-'+uuid4().hex
        self.state=Path('/root/K/F/evidence/fk')/(stem+'.json')
        self.log=Path(str(self.state)+'.events.jsonl')
        initialize_state(str(self.state))
        self.address='\0skill-'+uuid4().hex[:14]
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.thread=threading.Thread(target=fk_audit_gateway.serve_forever,kwargs={'address':self.address,'state_path':str(self.state),'log_path':str(self.log),'allowed_uid':os.getuid(),'stop_event':self.stop_event,'ready':self.ready.set},daemon=True)
        self.thread.start(); self.assertTrue(self.ready.wait(1.0))
    def tearDown(self):
        self.stop_event.set(); self.thread.join(timeout=1.0); self.assertFalse(self.thread.is_alive())
        self.state.unlink(missing_ok=True); self.log.unlink(missing_ok=True)
        seg=Path(str(self.log)+'.segments')
        if seg.exists():
            for x in seg.iterdir(): x.unlink(missing_ok=True)
            seg.rmdir()
    def _human(self,text):
        return append_remote_event(event_id='human-'+uuid4().hex[:8],kind='USER_NOTE',subject='human_chat',summary=text,address=self.address).generation
    def _proof(self,tool='files.read',reason='TEST_TRANSFER',success=True):
        payload={'schema':'K.COGNITION.CAPABILITY_AUDIT.1','tool':tool,'reason':reason,'verdict':'PASS' if success else 'VETO','receipt_sha256':hashlib.sha256(uuid4().bytes).hexdigest(),'verified':True if success else False,'executed':True if success else False,'fk_verdict':'PASS' if success else 'VETO'}
        return append_remote_event(event_id='cap-'+uuid4().hex[:8],kind='SYSTEM',subject='capability_evidence',summary=json.dumps(payload,sort_keys=True,separators=(',',':')),address=self.address).generation
    def _commit(self,revision):
        commit_skill_revision_event(event_id=revision.state['revision_id'],summary=json.dumps(revision.state,sort_keys=True,separators=(',',':'),ensure_ascii=False),address=self.address)
    def _candidate(self):
        self._human('读取第一份不同资料'); e1=self._proof()
        r1=build_revision(skill_id='files.read.transfer',description='在不同问题上下文中读取受控项目文件',status='CANDIDATE',confidence='LOW',evidence_sequences=[e1],reason='第一次真实成功执行',revision_id='skill-r1')
        self._commit(r1)
        return query_current_skills('读取 文件',address=self.address)[0],e1
    def test_candidate_requires_real_verified_execution(self):
        current,e1=self._candidate()
        self.assertEqual(current['status'],'CANDIDATE'); self.assertEqual(current['observed_successes'],1)
        self.assertEqual(current['distinct_transfer_contexts'],1); self.assertIn('files.read',current['observed_tools'])
    def test_validate_requires_three_distinct_transfer_contexts(self):
        current,e1=self._candidate()
        self._human('读取第二份不同资料'); e2=self._proof()
        self._human('读取第三份不同资料'); e3=self._proof()
        r2=build_revision(skill_id='files.read.transfer',description='在不同问题上下文中读取受控项目文件',status='VALIDATED',confidence='MEDIUM',evidence_sequences=[e2,e3],reason='三个不同真实任务均执行成功',previous=current,operation='VALIDATE',revision_id='skill-r2')
        self._commit(r2)
        got=query_current_skills('读取 文件',address=self.address)[0]
        self.assertEqual(got['status'],'VALIDATED'); self.assertGreaterEqual(got['observed_successes'],3); self.assertGreaterEqual(got['distinct_transfer_contexts'],3)
    def test_repeated_same_context_cannot_fake_transfer(self):
        current,e1=self._candidate()
        e2=self._proof(); e3=self._proof()
        bad=build_revision(skill_id='files.read.transfer',description='在不同问题上下文中读取受控项目文件',status='VALIDATED',confidence='MEDIUM',evidence_sequences=[e2,e3],reason='同一上下文重复不能冒充迁移',previous=current,operation='VALIDATE',revision_id='skill-r2')
        with self.assertRaises(AuditWitnessError): self._commit(bad)
    def test_degrade_requires_observed_negative_execution_evidence(self):
        current,e1=self._candidate()
        self._human('第二个任务'); e2=self._proof(); self._human('第三个任务'); e3=self._proof()
        valid=build_revision(skill_id='files.read.transfer',description='在不同问题上下文中读取受控项目文件',status='VALIDATED',confidence='MEDIUM',evidence_sequences=[e2,e3],reason='三次独立任务成功',previous=current,operation='VALIDATE',revision_id='skill-r2')
        self._commit(valid); current=query_current_skills('读取 文件',address=self.address)[0]
        self._human('新的失败任务'); neg=self._proof(success=False)
        degraded=build_revision(skill_id='files.read.transfer',description='该能力近期出现失败，需要重新验证',status='DEGRADED',confidence='LOW',evidence_sequences=[neg],reason='真实负向执行证据',previous=current,operation='DEGRADE',revision_id='skill-r3')
        self._commit(degraded)
        got=query_current_skills('files.read',address=self.address)[0]
        self.assertEqual(got['status'],'DEGRADED'); self.assertGreaterEqual(got['observed_failures'],1)
    def test_non_capability_event_cannot_be_skill_evidence(self):
        self._human('普通对话'); fake=append_remote_event(event_id='obs-x',kind='OBSERVATION',subject='test_evidence',summary='not an execution proof',address=self.address).generation
        r=build_revision(skill_id='fake.skill',description='不能由普通观察证明的技能',status='CANDIDATE',confidence='LOW',evidence_sequences=[fake],reason='伪证据测试',revision_id='skill-fake')
        with self.assertRaises(AuditWitnessError): self._commit(r)
    def test_ordinary_commit_cannot_bypass_skill_gate(self):
        from kk_k.audit_witness import _build_event_from_head, _parse_receipt, _request, query_witness
        self._human('真实任务'); e1=self._proof()
        rev=build_revision(skill_id='skill.bypass',description='不可绕过专用技能门',status='CANDIDATE',confidence='LOW',evidence_sequences=[e1],reason='测试',revision_id='skill-b1')
        head=query_witness(address=self.address)
        event=_build_event_from_head(head,event_id='skill-b1',kind='SYSTEM',subject='skill_revision',summary=json.dumps(rev.state,sort_keys=True,separators=(',',':'),ensure_ascii=False))
        with self.assertRaisesRegex(AuditWitnessError,'COGNITIVE_COMMIT_REQUIRED'):
            _parse_receipt(_request({'schema':'FK_AUDIT.COMMIT.2','event':event},self.address))

if __name__=='__main__': unittest.main()
