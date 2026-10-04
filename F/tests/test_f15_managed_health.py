import hashlib
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.managed_health import ManagedHealthError, evaluate_managed_health
from kk_f.managed_process import launch_managed

NOW = "2026-09-04T04:00:30Z"


class F15ManagedHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"; self.cwd.mkdir()
        self.exe = self.root / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\nimport sys,time\nif '--fail' in sys.argv: raise SystemExit(9)\nif '--clean' in sys.argv: raise SystemExit(0)\ntime.sleep(5)\n")
        self.exe.chmod(0o700)
        self.handles = []

    def tearDown(self):
        for h in self.handles:
            try: h.stop(grace_seconds=0.05)
            except Exception: pass
        self.tmp.cleanup()

    def spec(self, argv=None):
        return {"version":"0.1","executable":str(self.exe),"argv":list(argv or []),"cwd":str(self.cwd),"env":{},"sha256":hashlib.sha256(self.exe.read_bytes()).hexdigest()}

    def launch(self, argv=None):
        h=launch_managed(self.spec(argv)); self.handles.append(h); return h

    def hb(self, observed_at="2026-09-04T04:00:20Z", sequence=4):
        return {"version":"0.1","sequence":sequence,"observed_at":observed_at}

    def eval(self, h, hb=None):
        return evaluate_managed_health(h, self.hb() if hb is None else hb, now=NOW, healthy_within_seconds=15, degraded_within_seconds=30)

    def wait_not_running(self, h):
        deadline=time.monotonic()+3
        while h.observe()["status"]=="RUNNING" and time.monotonic()<deadline: time.sleep(0.01)

    def test_running_with_fresh_heartbeat_is_healthy(self):
        r=self.eval(self.launch())
        self.assertEqual(r["process_status"],"RUNNING"); self.assertEqual(r["status"],"HEALTHY")

    def test_running_with_aged_heartbeat_is_degraded(self):
        r=self.eval(self.launch(), self.hb("2026-09-04T04:00:10Z"))
        self.assertEqual(r["status"],"DEGRADED")

    def test_running_with_stale_heartbeat_is_failed(self):
        r=self.eval(self.launch(), self.hb("2026-09-04T03:59:59Z"))
        self.assertEqual(r["process_status"],"RUNNING"); self.assertEqual(r["status"],"FAILED")

    def test_process_existence_alone_never_claims_healthy(self):
        h=self.launch()
        with self.assertRaises(ManagedHealthError): self.eval(h, {"bad":True})

    def test_failed_process_remains_failed_without_using_heartbeat(self):
        h=self.launch(["--fail"]); self.wait_not_running(h)
        r=self.eval(h, {"bad":True})
        self.assertEqual(r["process_status"],"FAILED"); self.assertEqual(r["status"],"FAILED"); self.assertIsNone(r["heartbeat_sequence"])

    def test_cleanly_stopped_process_remains_stopped(self):
        h=self.launch(["--clean"]); self.wait_not_running(h)
        r=self.eval(h, {"bad":True})
        self.assertEqual(r["status"],"STOPPED")

    def test_future_heartbeat_rejected_fail_closed(self):
        with self.assertRaises(ManagedHealthError): self.eval(self.launch(), self.hb("2026-09-04T04:00:31Z"))

    def test_invalid_threshold_rejected_fail_closed(self):
        h=self.launch()
        with self.assertRaises(ManagedHealthError):
            evaluate_managed_health(h,self.hb(),now=NOW,healthy_within_seconds=0,degraded_within_seconds=30)

    def test_invalid_current_type_rejected(self):
        with self.assertRaises(ManagedHealthError):
            evaluate_managed_health(object(),self.hb(),now=NOW,healthy_within_seconds=15,degraded_within_seconds=30)


if __name__ == "__main__": unittest.main()
