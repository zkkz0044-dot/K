import hashlib
import json
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.evidence import EvidenceError, initialize as init_evidence, verify
from kk_f.health_supervisor import HealthSupervisionResult, supervise_once
from kk_f.managed_process import launch_managed
from kk_f.restart_ledger import initialize as init_ledger
from kk_f.supervision_evidence import SupervisionEvidenceError, record_supervision

MID="123e4567-e89b-42d3-a456-426614174017"
TS="2026-09-04T05:30:00Z"


class F17SupervisionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.tmp.name)
        self.store=self.root/'evidence'; init_evidence(self.store)
        self.ledger=self.root/'ledger'; init_ledger(str(self.ledger),2)
        self.cwd=self.root/'work'; self.cwd.mkdir(); self.exe=self.root/'worker.py'
        self.exe.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(5)\n"); self.exe.chmod(0o700); self.handles=[]
    def tearDown(self):
        for h in self.handles:
            try:h.stop(grace_seconds=0.05)
            except Exception:pass
        self.tmp.cleanup()
    def spec(self):
        return {'version':'0.1','executable':str(self.exe),'argv':[],'cwd':str(self.cwd),'env':{},'sha256':hashlib.sha256(self.exe.read_bytes()).hexdigest()}
    def launch(self):
        h=launch_managed(self.spec()); self.handles.append(h); return h
    def synthetic(self,status='HEALTHY'):
        return HealthSupervisionResult(status,'RUNNING','NO_ACTION',-1,False,None)

    def test_healthy_result_appends_one_valid_f02_record(self):
        digest=record_supervision(str(self.store),self.synthetic(),message_id=MID,timestamp=TS)
        state=verify(self.store); self.assertEqual(state['count'],1); self.assertEqual(state['last_hash'],digest)

    def test_record_has_frozen_supervisor_to_operator_roles(self):
        record_supervision(str(self.store),self.synthetic(),message_id=MID,timestamp=TS)
        entry=json.loads((self.store/'evidence.jsonl').read_text())
        record=entry['record']; self.assertEqual(record['source_role'],'supervisor'); self.assertEqual(record['target_role'],'operator'); self.assertEqual(record['kind'],'result')

    def test_status_and_payload_exactly_capture_outcome(self):
        r=HealthSupervisionResult('DEGRADED','RUNNING','NO_ACTION',-1,False,None)
        record_supervision(str(self.store),r,message_id=MID,timestamp=TS)
        p=json.loads((self.store/'evidence.jsonl').read_text())['record']
        self.assertEqual(p['status'],'DEGRADED'); self.assertEqual(p['payload'],{'attempts':-1,'contained':False,'decision':'NO_ACTION','process_status':'RUNNING','replacement_pid':None})

    def test_real_f16_failed_replacement_records_replacement_pid(self):
        h=self.launch(); hb={'version':'0.1','sequence':1,'observed_at':'2026-09-04T05:00:00Z'}
        r=supervise_once(str(self.ledger),h,hb,self.spec(),now='2026-09-04T05:01:00Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1)
        self.assertIsNotNone(r.replacement); self.handles.append(r.replacement)
        record_supervision(str(self.store),r,message_id=MID,timestamp=TS)
        record=json.loads((self.store/'evidence.jsonl').read_text())['record']
        self.assertEqual(record['status'],'FAILED'); self.assertTrue(record['payload']['contained']); self.assertEqual(record['payload']['replacement_pid'],r.replacement.pid)

    def test_invalid_message_id_rejected_without_mutation(self):
        with self.assertRaises(SupervisionEvidenceError): record_supervision(str(self.store),self.synthetic(),message_id='BAD',timestamp=TS)
        self.assertEqual(verify(self.store)['count'],0)

    def test_invalid_timestamp_rejected_without_mutation(self):
        with self.assertRaises(SupervisionEvidenceError): record_supervision(str(self.store),self.synthetic(),message_id=MID,timestamp='not-time')
        self.assertEqual(verify(self.store)['count'],0)

    def test_wrong_result_type_rejected_without_mutation(self):
        with self.assertRaises(SupervisionEvidenceError): record_supervision(str(self.store),object(),message_id=MID,timestamp=TS)
        self.assertEqual(verify(self.store)['count'],0)

    def test_corrupt_store_blocks_append(self):
        (self.store/'HEAD.json').write_text('corrupt\n')
        with self.assertRaises(SupervisionEvidenceError): record_supervision(str(self.store),self.synthetic(),message_id=MID,timestamp=TS)


if __name__=='__main__':unittest.main()
