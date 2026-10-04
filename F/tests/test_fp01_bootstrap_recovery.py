import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.frozen_authority import build_frozen_authority

from kk_f.managed_process import ManagedProcessError
from kk_f.restart_ledger import (
    RestartLedgerError,
    evaluate_and_record,
    initialize,
    read_ledger,
    rollback_pristine_initialization,
)
from kk_f.runtime_bootstrap import RuntimeBootstrapError, bootstrap_runtime


class FP01BootstrapRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.ledger = self.root / "ledger"
        self.exe = self.root / "worker.py"
        self.exe.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(5)\n")
        self.exe.chmod(0o700)
        self.digest = hashlib.sha256(self.exe.read_bytes()).hexdigest()
        self.auth = self.root / "authority.json"
        self.auth.write_text(json.dumps(build_frozen_authority("kk-f-root", self.spec(), 2), separators=(",", ":")) + "\n")
        self.auth.chmod(0o600)
        self.handles = []
        self.locks = []

    def tearDown(self):
        for handle in self.handles:
            try:
                handle.stop(grace_seconds=0.05)
            except Exception:
                pass
        for lock in self.locks:
            try:
                lock.release()
            except Exception:
                pass
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

    @staticmethod
    def transient_spawn_failure(*args, **kwargs):
        try:
            raise OSError("simulated transient spawn resource failure")
        except OSError as cause:
            raise ManagedProcessError("managed process launch failed") from cause

    def test_transient_spawn_failure_rolls_back_pristine_ledger(self):
        with mock.patch("kk_f.runtime_bootstrap.launch_managed", side_effect=self.transient_spawn_failure):
            with self.assertRaises(RuntimeBootstrapError):
                bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        self.assertFalse((self.ledger / "checkpoint.json").exists())

    def test_retry_succeeds_after_transient_spawn_failure(self):
        with mock.patch("kk_f.runtime_bootstrap.launch_managed", side_effect=self.transient_spawn_failure):
            with self.assertRaises(RuntimeBootstrapError):
                bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        result = bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        self.handles.append(result.worker)
        self.locks.append(result.instance_lock)
        self.assertEqual(result.worker.observe()["status"], "RUNNING")
        self.assertEqual(read_ledger(str(self.ledger))["attempts"], 0)

    def test_rollback_refuses_mutated_generation(self):
        initialize(str(self.ledger), 2)
        evaluate_and_record(str(self.ledger), "RUNNING")
        before = read_ledger(str(self.ledger))
        with self.assertRaises(RestartLedgerError):
            rollback_pristine_initialization(str(self.ledger), 2)
        self.assertEqual(read_ledger(str(self.ledger)), before)

    def test_rollback_refuses_budget_mismatch(self):
        initialize(str(self.ledger), 2)
        with self.assertRaises(RestartLedgerError):
            rollback_pristine_initialization(str(self.ledger), 3)
        self.assertEqual(read_ledger(str(self.ledger))["max_attempts"], 2)

    def test_preflight_failure_occurs_before_ledger_creation(self):
        self.exe.write_text(self.exe.read_text() + "# tampered\n")
        with self.assertRaises(RuntimeBootstrapError):
            bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        self.assertFalse(self.ledger.exists())

    def test_abandoned_pristine_ledger_is_recovered_when_lock_is_free(self):
        initialize(str(self.ledger), 2)
        result = bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        self.handles.append(result.worker)
        self.locks.append(result.instance_lock)
        self.assertEqual(result.worker.observe()["status"], "RUNNING")
        self.assertEqual(read_ledger(str(self.ledger))["generation"], 0)

    def test_non_os_launch_failure_keeps_ledger_fail_closed(self):
        def integrity_failure(*args, **kwargs):
            raise ManagedProcessError("synthetic non-OS launch failure")
        with mock.patch("kk_f.runtime_bootstrap.launch_managed", side_effect=integrity_failure):
            with self.assertRaises(RuntimeBootstrapError):
                bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        self.assertEqual(read_ledger(str(self.ledger))["generation"], 0)

    def test_spawn_failure_after_ledger_mutation_refuses_rollback(self):
        def mutate_then_fail(*args, **kwargs):
            evaluate_and_record(str(self.ledger), "RUNNING")
            return self.transient_spawn_failure()
        with mock.patch("kk_f.runtime_bootstrap.launch_managed", side_effect=mutate_then_fail):
            with self.assertRaises(RuntimeBootstrapError):
                bootstrap_runtime(str(self.auth), str(self.ledger), self.spec())
        self.assertEqual(read_ledger(str(self.ledger))["generation"], 1)


if __name__ == "__main__":
    unittest.main()
