import hashlib
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.health_supervisor import HealthSupervisorError, supervise_once
from kk_f.managed_process import launch_managed
from kk_f.restart_ledger import evaluate_and_record, initialize, read_ledger

NOW="2026-09-04T05:00:30Z"


class F16HealthSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.tmp.name)
        self.cwd=self.root/'work'; self.cwd.mkdir(); self.ledger=self.root/'ledger'
        self.exe=self.root/'worker.py'
        self.exe.write_text("#!/usr/bin/python3\nimport pathlib,sys,time\nif '--mark' in sys.argv: pathlib.Path('started').write_text('yes')\nif '--fail' in sys.argv: raise SystemExit(8)\ntime.sleep(5)\n")
        self.exe.chmod(0o700); self.handles=[]
    def tearDown(self):
        for h in self.handles:
            try:h.stop(grace_seconds=0.05)
            except Exception:pass
        self.tmp.cleanup()
    def spec(self,argv=None):
        return {'version':'0.1','executable':str(self.exe),'argv':list(argv or []),'cwd':str(self.cwd),'env':{},'sha256':hashlib.sha256(self.exe.read_bytes()).hexdigest()}
    def launch(self,argv=None):
        h=launch_managed(self.spec(argv)); self.handles.append(h); return h
    def hb(self,ts): return {'version':'0.1','sequence':1,'observed_at':ts}
    def supervise(self,h,hb,repl=None,grace=0.1):
        return supervise_once(str(self.ledger),h,hb,self.spec(['--mark']) if repl is None else repl,now=NOW,healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=grace)
    def wait_failed(self,h):
        deadline=time.monotonic()+3
        while h.observe()['status']=='RUNNING' and time.monotonic()<deadline: time.sleep(0.01)
        self.assertEqual(h.observe()['status'],'FAILED')

    def test_healthy_process_not_contained_and_ledger_untouched(self):
        initialize(str(self.ledger),2); h=self.launch(); before=read_ledger(str(self.ledger))
        r=self.supervise(h,self.hb('2026-09-04T05:00:20Z'))
        self.assertEqual(r.health_status,'HEALTHY'); self.assertFalse(r.contained); self.assertIsNone(r.replacement)
        self.assertEqual(read_ledger(str(self.ledger)),before); self.assertEqual(h.observe()['status'],'RUNNING')

    def test_degraded_process_not_contained(self):
        initialize(str(self.ledger),2); h=self.launch(); before=read_ledger(str(self.ledger))
        r=self.supervise(h,self.hb('2026-09-04T05:00:10Z'))
        self.assertEqual(r.health_status,'DEGRADED'); self.assertEqual(read_ledger(str(self.ledger)),before)
        self.assertEqual(h.observe()['status'],'RUNNING')

    def test_stale_running_process_is_contained_then_replaced(self):
        initialize(str(self.ledger),2); h=self.launch()
        r=self.supervise(h,self.hb('2026-09-04T04:59:59Z'))
        self.assertEqual(r.health_status,'FAILED'); self.assertTrue(r.contained); self.assertEqual(r.decision,'REPLACE_INSTANCE'); self.assertEqual(r.attempts,1)
        self.assertEqual(h.observe()['status'],'FAILED')
        self.assertIsNotNone(r.replacement); self.handles.append(r.replacement)

    def test_crashed_process_replaced_without_containment(self):
        initialize(str(self.ledger),2); h=self.launch(['--fail']); self.wait_failed(h)
        r=self.supervise(h,{'bad':True})
        self.assertFalse(r.contained); self.assertEqual(r.decision,'REPLACE_INSTANCE'); self.assertIsNotNone(r.replacement); self.handles.append(r.replacement)

    def test_exhausted_budget_contains_stale_but_holds_failed(self):
        initialize(str(self.ledger),1); evaluate_and_record(str(self.ledger),'FAILED')
        h=self.launch(); r=self.supervise(h,self.hb('2026-09-04T04:59:59Z'))
        self.assertTrue(r.contained); self.assertEqual(r.decision,'HOLD_FAILED'); self.assertIsNone(r.replacement); self.assertEqual(r.attempts,1)

    def test_invalid_heartbeat_fails_closed_without_containment_or_ledger_mutation(self):
        initialize(str(self.ledger),2); h=self.launch(); before=read_ledger(str(self.ledger))
        with self.assertRaises(HealthSupervisorError): self.supervise(h,{'bad':True})
        self.assertEqual(h.observe()['status'],'RUNNING'); self.assertEqual(read_ledger(str(self.ledger)),before)

    def test_invalid_grace_blocks_before_budget_consumption(self):
        initialize(str(self.ledger),2); h=self.launch(); before=read_ledger(str(self.ledger))
        with self.assertRaises(HealthSupervisorError): self.supervise(h,self.hb('2026-09-04T04:59:59Z'),grace=0)
        self.assertEqual(h.observe()['status'],'RUNNING'); self.assertEqual(read_ledger(str(self.ledger)),before)

    def test_hash_mutation_after_stale_evidence_consumes_attempt_but_no_replacement(self):
        initialize(str(self.ledger),2); h=self.launch(); repl=self.spec(['--mark']); self.exe.write_text(self.exe.read_text()+'#changed\n')
        with self.assertRaises(HealthSupervisorError): self.supervise(h,self.hb('2026-09-04T04:59:59Z'),repl=repl)
        self.assertNotEqual(h.observe()['status'],'RUNNING'); ledger=read_ledger(str(self.ledger)); self.assertEqual(ledger['attempts'],1)
        self.assertFalse((self.cwd/'started').exists())


if __name__=='__main__': unittest.main()
