import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kk_f.evidence import verify as verify_evidence
from kk_f.production_daemon import ProductionDaemonError, load_runtime_config, run_daemon

class FP06ProductionDaemonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.work = self.root / "work"; self.work.mkdir()
        self.runtime = self.root / "runtime"; self.runtime.mkdir()
        self.heartbeat = self.runtime / "heartbeat.json"
        self.worker = self.root / "worker.py"
        self.worker.write_text(
            "#!/usr/bin/python3\n"
            "import json,os,time,pathlib,datetime\n"
            "p=pathlib.Path(os.environ['HEARTBEAT'])\n"
            "seq=0\n"
            "while True:\n"
            " seq+=1; now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')\n"
            " tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps({'version':'0.1','sequence':seq,'observed_at':now})); tmp.replace(p); time.sleep(0.02)\n"
        )
        self.worker.chmod(0o755)
        self.digest = hashlib.sha256(self.worker.read_bytes()).hexdigest()
        self.spec = {"version":"0.1","executable":str(self.worker),"argv":[],"cwd":str(self.work),"env":{"HEARTBEAT":str(self.heartbeat)},"sha256":self.digest}
        self.auth = self.root / "authority.json"
        self.auth.write_text(json.dumps({"version":"0.2","authority_id":"fp06-unit","process_spec":self.spec,"max_restart_attempts":2},separators=(",",":"))+"\n")
        self.auth.chmod(0o644)
        self.ledger = self.root / "ledger"
        self.evidence = self.root / "evidence"
        self.config = self.root / "runtime.json"
        self.config.write_text(json.dumps({
            "version":"0.1","authority_path":str(self.auth),"ledger_directory":str(self.ledger),
            "evidence_directory":str(self.evidence),"heartbeat_path":str(self.heartbeat),"process_spec":self.spec,
            "healthy_within_seconds":1,"degraded_within_seconds":2,"grace_seconds":0.05,
            "base_delay_seconds":0.05,"max_delay_seconds":0.2,"poll_interval_seconds":0.03,
            "heartbeat_startup_grace_seconds":3.0
        },separators=(",",":"))+"\n")
        self.config.chmod(0o644)

    def tearDown(self):
        self.tmp.cleanup()

    def test_config_requires_root_owned_regular_nonwritable_file(self):
        cfg = load_runtime_config(str(self.config))
        self.assertEqual(cfg.authority_path, str(self.auth))
        self.config.chmod(0o666)
        with self.assertRaises(ProductionDaemonError):
            load_runtime_config(str(self.config))

    def test_cold_start_real_worker_real_heartbeat_and_graceful_cleanup(self):
        rc = run_daemon(str(self.config), stop_after_cycles=120)
        self.assertEqual(rc, 0)
        verified = verify_evidence(str(self.evidence))
        self.assertGreaterEqual(verified["count"], 1)
        self.assertFalse((self.ledger / "checkpoint.json").exists())

    def test_existing_corrupt_ledger_fails_closed(self):
        self.ledger.mkdir(); (self.ledger / "checkpoint.json").write_text("corrupt\n")
        with self.assertRaises(ProductionDaemonError):
            run_daemon(str(self.config), stop_after_cycles=1)

    def test_existing_corrupt_evidence_fails_closed_before_worker(self):
        self.evidence.mkdir(); (self.evidence / "HEAD.json").write_text("corrupt\n")
        with mock.patch("kk_f.production_daemon.launch_managed", side_effect=AssertionError("must not launch")):
            with self.assertRaises(ProductionDaemonError):
                run_daemon(str(self.config), stop_after_cycles=1)

if __name__ == "__main__":
    unittest.main()
