import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.frozen_authority import build_frozen_authority

from kk_f.instance_lock import InstanceLockError, acquire_instance_lock
from kk_f.restart_ledger import evaluate_and_record, initialize, read_ledger
from kk_f.runtime_bootstrap import RuntimeBootstrapError, bootstrap_runtime


class FP02InstanceLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.lock_path = self.root / "f-runtime.lock"
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

    def test_first_holder_acquires_and_second_holder_is_denied(self):
        one = acquire_instance_lock(self.lock_path)
        self.locks.append(one)
        with self.assertRaises(InstanceLockError):
            acquire_instance_lock(self.lock_path)

    def test_release_is_idempotent_and_file_can_be_reacquired(self):
        one = acquire_instance_lock(self.lock_path)
        one.release()
        one.release()
        two = acquire_instance_lock(self.lock_path)
        self.locks.append(two)
        self.assertFalse(two.released)

    def test_stale_unlocked_file_requires_no_manual_deletion(self):
        self.lock_path.write_text('{"pid":999999}\n')
        self.lock_path.chmod(0o600)
        lock = acquire_instance_lock(self.lock_path)
        self.locks.append(lock)
        metadata = json.loads(self.lock_path.read_text())
        self.assertEqual(metadata["pid"], os.getpid())

    def test_relative_path_rejected(self):
        with self.assertRaises(InstanceLockError):
            acquire_instance_lock("relative.lock")

    def test_symlink_lock_rejected(self):
        target = self.root / "target"
        target.write_text("x")
        self.lock_path.symlink_to(target)
        with self.assertRaises(InstanceLockError):
            acquire_instance_lock(self.lock_path)

    def test_group_writable_existing_lock_rejected(self):
        self.lock_path.write_text("x")
        self.lock_path.chmod(0o620)
        with self.assertRaises(InstanceLockError):
            acquire_instance_lock(self.lock_path)

    def test_real_other_process_contention(self):
        script = self.root / "holder.py"
        script.write_text(
            "import sys,time\n"
            "sys.path.insert(0," + repr(str(pathlib.Path(__file__).resolve().parents[1] / 'src')) + ")\n"
            "from kk_f.instance_lock import acquire_instance_lock\n"
            "lock=acquire_instance_lock(sys.argv[1])\n"
            "print('LOCKED',flush=True)\n"
            "time.sleep(3)\n"
        )
        proc = subprocess.Popen([sys.executable, str(script), str(self.lock_path)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(InstanceLockError):
                acquire_instance_lock(self.lock_path)
        finally:
            proc.terminate()
            proc.wait(timeout=2)
            if proc.stdout is not None:
                proc.stdout.close()
        lock = acquire_instance_lock(self.lock_path)
        self.locks.append(lock)

    def test_live_bootstrap_lock_blocks_second_bootstrap_without_ledger_mutation(self):
        first = bootstrap_runtime(str(self.auth), str(self.ledger), self.spec(), lock_path=str(self.lock_path))
        self.handles.append(first.worker)
        self.locks.append(first.instance_lock)
        before = read_ledger(str(self.ledger))
        with self.assertRaises(RuntimeBootstrapError):
            bootstrap_runtime(str(self.auth), str(self.ledger), self.spec(), lock_path=str(self.lock_path))
        self.assertEqual(read_ledger(str(self.ledger)), before)

    def test_abandoned_pristine_ledger_is_recovered_under_free_lock(self):
        initialize(str(self.ledger), 2)
        result = bootstrap_runtime(str(self.auth), str(self.ledger), self.spec(), lock_path=str(self.lock_path))
        self.handles.append(result.worker)
        self.locks.append(result.instance_lock)
        self.assertEqual(result.worker.observe()["status"], "RUNNING")
        self.assertEqual(read_ledger(str(self.ledger))["generation"], 0)

    def test_nonpristine_ledger_is_never_reset_even_when_lock_is_free(self):
        initialize(str(self.ledger), 2)
        evaluate_and_record(str(self.ledger), "RUNNING")
        before = read_ledger(str(self.ledger))
        with self.assertRaises(RuntimeBootstrapError):
            bootstrap_runtime(str(self.auth), str(self.ledger), self.spec(), lock_path=str(self.lock_path))
        self.assertEqual(read_ledger(str(self.ledger)), before)
        # bootstrap failure must release its acquired lock
        lock = acquire_instance_lock(self.lock_path)
        self.locks.append(lock)


if __name__ == "__main__":
    unittest.main()
