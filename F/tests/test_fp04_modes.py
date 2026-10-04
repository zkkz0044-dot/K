import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.frozen_authority import build_frozen_authority

from kk_f.dry_run import DryRunError, plan_runtime_action
from kk_f.evidence import initialize as initialize_evidence
from kk_f.restart_ledger import evaluate_and_record, initialize, read_ledger
from kk_f.self_test import SelfTestError, run_isolated_self_test


class FP04ModesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.exe = self.root / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(5)\n")
        self.exe.chmod(0o700)
        self.digest = hashlib.sha256(self.exe.read_bytes()).hexdigest()
        self.auth = self.root / "authority.json"
        self.auth.write_text(json.dumps(build_frozen_authority("kk-f-selftest", self.spec(), 3), separators=(",", ":")) + "\n")
        self.auth.chmod(0o600)
        self.ledger = self.root / "ledger"
        self.evidence = self.root / "evidence"

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self):
        return {
            "version": "0.1",
            "executable": str(self.exe),
            "argv": [],
            "cwd": str(self.cwd),
            "env": {},
            "sha256": self.digest,
        }

    def test_dry_run_recomputes_real_disk_sha256(self):
        initialize(str(self.ledger), 3)
        plan = plan_runtime_action(str(self.auth), str(self.ledger), self.spec(), "FAILED", now="2026-09-04T09:30:00Z")
        self.assertEqual(plan.verified_sha256, hashlib.sha256(self.exe.read_bytes()).hexdigest())
        self.exe.write_text(self.exe.read_text() + "# tampered\n")
        with self.assertRaises(DryRunError):
            plan_runtime_action(str(self.auth), str(self.ledger), self.spec(), "FAILED", now="2026-09-04T09:30:00Z")

    def test_dry_run_is_byte_for_byte_read_only(self):
        initialize(str(self.ledger), 3)
        evaluate_and_record(str(self.ledger), "FAILED", attempted_at="2026-09-04T09:29:55Z")
        checkpoint = self.ledger / "checkpoint.json"
        before = checkpoint.read_bytes()
        plan = plan_runtime_action(
            str(self.auth), str(self.ledger), self.spec(), "FAILED",
            now="2026-09-04T09:30:00Z", base_delay_seconds=10, max_delay_seconds=60,
        )
        self.assertEqual(plan.decision, "WAIT_BACKOFF")
        self.assertEqual(checkpoint.read_bytes(), before)

    def test_dry_run_never_calls_popen_or_mutating_ledger_api(self):
        initialize(str(self.ledger), 3)
        with mock.patch("subprocess.Popen", side_effect=AssertionError("Popen forbidden")) as popen, \
             mock.patch("kk_f.restart_ledger.evaluate_and_record", side_effect=AssertionError("mutation forbidden")) as mutate:
            plan = plan_runtime_action(str(self.auth), str(self.ledger), self.spec(), "FAILED", now="2026-09-04T09:30:00Z")
        self.assertEqual(plan.decision, "REPLACE_INSTANCE")
        popen.assert_not_called()
        mutate.assert_not_called()

    def test_dry_run_does_not_touch_evidence(self):
        initialize(str(self.ledger), 3)
        initialize_evidence(str(self.evidence))
        head = (self.evidence / "HEAD.json").read_bytes()
        log = (self.evidence / "evidence.jsonl").read_bytes()
        plan_runtime_action(str(self.auth), str(self.ledger), self.spec(), "RUNNING", now="2026-09-04T09:30:00Z")
        self.assertEqual((self.evidence / "HEAD.json").read_bytes(), head)
        self.assertEqual((self.evidence / "evidence.jsonl").read_bytes(), log)

    def test_self_test_requires_its_own_valid_authority(self):
        bad_auth = self.root / "bad-authority.json"
        bad_auth.write_text(self.auth.read_text().replace(self.digest, "f" * 64))
        bad_auth.chmod(0o600)
        with self.assertRaises(SelfTestError):
            run_isolated_self_test(
                str(self.root), str(bad_auth), str(self.ledger), str(self.evidence), self.spec(),
                now="2026-09-04T09:30:00Z",
            )
        self.assertFalse(self.ledger.exists())

    def test_self_test_rejects_paths_outside_isolation_root(self):
        with self.assertRaises(SelfTestError):
            run_isolated_self_test(
                str(self.cwd), str(self.auth), str(self.ledger), str(self.evidence), self.spec(),
                now="2026-09-04T09:30:00Z",
            )

    def test_self_test_uses_real_popen_and_real_isolated_evidence(self):
        original = subprocess.Popen
        with mock.patch("subprocess.Popen", wraps=original) as popen:
            result = run_isolated_self_test(
                str(self.root), str(self.auth), str(self.ledger), str(self.evidence), self.spec(),
                now="2026-09-04T09:30:00Z",
            )
        self.assertGreater(result.worker_pid, 0)
        self.assertEqual(result.health_status, "HEALTHY")
        self.assertEqual(result.evidence_count, 1)
        self.assertTrue(popen.called)
        self.assertEqual(read_ledger(str(self.ledger))["attempts"], 0)
        self.assertEqual((self.evidence / "evidence.jsonl").read_text().count("\n"), 1)

    def test_self_test_refuses_existing_mutable_namespace(self):
        initialize(str(self.ledger), 3)
        with self.assertRaises(SelfTestError):
            run_isolated_self_test(
                str(self.root), str(self.auth), str(self.ledger), str(self.evidence), self.spec(),
                now="2026-09-04T09:30:00Z",
            )

    def test_dry_run_creates_no_runtime_lock(self):
        initialize(str(self.ledger), 3)
        default_lock = self.ledger.with_name(self.ledger.name + ".lock")
        plan_runtime_action(str(self.auth), str(self.ledger), self.spec(), "FAILED", now="2026-09-04T09:30:00Z")
        self.assertFalse(default_lock.exists())

    def test_self_test_reaps_worker_before_return(self):
        import os
        result = run_isolated_self_test(
            str(self.root), str(self.auth), str(self.ledger), str(self.evidence), self.spec(),
            now="2026-09-04T09:30:00Z",
        )
        with self.assertRaises(ProcessLookupError):
            os.kill(result.worker_pid, 0)


if __name__ == "__main__":
    unittest.main()
