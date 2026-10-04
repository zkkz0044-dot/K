import hashlib
import json
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.frozen_authority import build_frozen_authority

from kk_f.evidence import initialize as init_evidence, verify as verify_evidence
from kk_f.restart_ledger import read_ledger
from kk_f.runtime_bootstrap import bootstrap_runtime
from kk_f.runtime_cycle import RuntimeCycleError, run_cycle


class F20RuntimeCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.cwd=self.root/'work';self.cwd.mkdir();self.ledger=self.root/'ledger';self.store=self.root/'evidence';init_evidence(self.store)
        self.exe=self.root/'worker.py';self.exe.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(5)\n");self.exe.chmod(0o700)
        self.digest=hashlib.sha256(self.exe.read_bytes()).hexdigest();self.auth=self.root/'authority.json'
        self.manifest=build_frozen_authority('kk-f-root',self.spec(),2)
        self.auth.write_text(json.dumps(self.manifest,separators=(',',':'))+'\n');self.auth.chmod(0o600)
        boot=bootstrap_runtime(str(self.auth),str(self.ledger),self.spec());self.current=boot.worker;self.instance_lock=boot.instance_lock;self.handles=[self.current]
    def tearDown(self):
        for h in self.handles:
            if h is None:continue
            try:h.stop(grace_seconds=0.05)
            except Exception:pass
        try:self.instance_lock.release()
        except Exception:pass
        self.tmp.cleanup()
    def spec(self):
        return {'version':'0.1','executable':str(self.exe),'argv':[],'cwd':str(self.cwd),'env':{},'sha256':self.digest}
    def hb(self,seq,ts):return {'version':'0.1','sequence':seq,'observed_at':ts}
    def cycle(self,hb,prev=None,mid='123e4567-e89b-42d3-a456-426614174020',now='2026-09-04T06:00:30Z'):
        return run_cycle(str(self.auth),str(self.ledger),str(self.store),self.current,hb,self.spec(),previous_heartbeat=prev,now=now,healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id=mid,timestamp=now)

    def test_first_fresh_cycle_is_healthy_audited_and_keeps_worker(self):
        hb=self.hb(1,'2026-09-04T06:00:20Z');r=self.cycle(hb)
        self.assertEqual(r.supervision.health_status,'HEALTHY');self.assertIs(r.current,self.current);self.assertEqual(r.accepted_heartbeat,hb)
        self.assertEqual(verify_evidence(self.store)['count'],1);self.assertEqual(read_ledger(str(self.ledger))['attempts'],0)
    def test_monotonic_second_cycle_appends_second_evidence_record(self):
        one=self.hb(1,'2026-09-04T06:00:10Z');r1=self.cycle(one)
        two=self.hb(2,'2026-09-04T06:00:20Z');r2=self.cycle(two,r1.accepted_heartbeat,mid='223e4567-e89b-42d3-a456-426614174020')
        self.assertEqual(r2.supervision.health_status,'HEALTHY');self.assertEqual(verify_evidence(self.store)['count'],2)
    def test_replayed_heartbeat_rejected_before_action_or_evidence(self):
        prev=self.hb(1,'2026-09-04T06:00:20Z');before_ledger=read_ledger(str(self.ledger));before_evidence=verify_evidence(self.store)
        with self.assertRaises(RuntimeCycleError):self.cycle(dict(prev),prev)
        self.assertEqual(read_ledger(str(self.ledger)),before_ledger);self.assertEqual(verify_evidence(self.store),before_evidence);self.assertEqual(self.current.observe()['status'],'RUNNING')
    def test_identical_poll_snapshot_can_be_resampled_without_weakening_default_gate(self):
        prev=self.hb(1,'2026-09-04T06:00:20Z')
        r=run_cycle(str(self.auth),str(self.ledger),str(self.store),self.current,dict(prev),self.spec(),previous_heartbeat=prev,now='2026-09-04T06:00:21Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id='323e4567-e89b-42d3-a456-426614174020',timestamp='2026-09-04T06:00:21Z',_allow_identical_poll_snapshot=True)
        self.assertEqual(r.accepted_heartbeat,prev);self.assertEqual(r.supervision.health_status,'HEALTHY');self.assertEqual(verify_evidence(self.store)['count'],1)
    def test_poll_mode_still_rejects_same_sequence_with_changed_record(self):
        prev=self.hb(1,'2026-09-04T06:00:20Z');changed=self.hb(1,'2026-09-04T06:00:21Z')
        with self.assertRaises(RuntimeCycleError):
            run_cycle(str(self.auth),str(self.ledger),str(self.store),self.current,changed,self.spec(),previous_heartbeat=prev,now='2026-09-04T06:00:22Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id='423e4567-e89b-42d3-a456-426614174020',timestamp='2026-09-04T06:00:22Z',_allow_identical_poll_snapshot=True)
        self.assertEqual(verify_evidence(self.store)['count'],0)
    def test_stale_heartbeat_contains_replaces_accounts_and_audits(self):
        hb=self.hb(1,'2026-09-04T05:59:59Z');r=self.cycle(hb)
        self.assertEqual(r.supervision.health_status,'FAILED');self.assertTrue(r.supervision.contained);self.assertEqual(r.supervision.decision,'REPLACE_INSTANCE')
        self.assertIsNotNone(r.current);self.assertNotEqual(r.current.pid,self.current.pid);self.handles.append(r.current)
        self.assertEqual(read_ledger(str(self.ledger))['attempts'],1);self.assertEqual(verify_evidence(self.store)['count'],1)
    def test_mutable_authority_rejected_before_heartbeat_or_action(self):
        self.auth.chmod(0o622);before_ledger=read_ledger(str(self.ledger));before_evidence=verify_evidence(self.store)
        with self.assertRaises(RuntimeCycleError):self.cycle(self.hb(1,'2026-09-04T06:00:20Z'))
        self.assertEqual(read_ledger(str(self.ledger)),before_ledger);self.assertEqual(verify_evidence(self.store),before_evidence);self.assertEqual(self.current.observe()['status'],'RUNNING')
    def test_authority_budget_mismatch_rejected(self):
        changed=dict(self.manifest,max_restart_attempts=3);self.auth.write_text(json.dumps(changed));self.auth.chmod(0o600)
        with self.assertRaises(RuntimeCycleError):self.cycle(self.hb(1,'2026-09-04T06:00:20Z'))
        self.assertEqual(read_ledger(str(self.ledger))['attempts'],0);self.assertEqual(verify_evidence(self.store)['count'],0)
    def test_corrupt_evidence_store_after_replacement_stops_new_replacement_and_fails_closed(self):
        (self.store/'HEAD.json').write_text('corrupt\n');hb=self.hb(1,'2026-09-04T05:59:59Z')
        with self.assertRaises(RuntimeCycleError):self.cycle(hb)
        self.assertNotEqual(self.current.observe()['status'],'RUNNING');self.assertEqual(read_ledger(str(self.ledger))['attempts'],1)
    def test_invalid_message_id_after_healthy_supervision_fails_without_killing_current(self):
        with self.assertRaises(RuntimeCycleError):self.cycle(self.hb(1,'2026-09-04T06:00:20Z'),mid='BAD')
        self.assertEqual(self.current.observe()['status'],'RUNNING');self.assertEqual(read_ledger(str(self.ledger))['attempts'],0);self.assertEqual(verify_evidence(self.store)['count'],0)
    def test_no_external_service_is_needed_for_real_local_cycle(self):
        r=self.cycle(self.hb(1,'2026-09-04T06:00:20Z'))
        self.assertEqual(r.supervision.health_status,'HEALTHY');self.assertGreater(r.current.pid,0)


if __name__=='__main__':unittest.main()
