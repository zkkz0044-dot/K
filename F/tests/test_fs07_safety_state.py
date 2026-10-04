import json,tempfile,unittest
from pathlib import Path
from unittest import mock
from kk_f.safety_state import *
from kk_f.release_recovery import ReleaseRecoveryError
class SafetyTests(unittest.TestCase):
    def setUp(self):self.td=tempfile.TemporaryDirectory();self.root=Path(self.td.name)/"safe";initialize_safety_state(self.root)
    def tearDown(self):self.td.cleanup()
    def call(self,threshold=3):return guarded_reconcile(self.root,"/store","/ptr","/state",{},failure_threshold=threshold)
    def test_initial_state_exact_normal(self):
        s=read_safety_state(self.root);self.assertEqual(s["mode"],"NORMAL");self.assertEqual(s["generation"],0);self.assertEqual(s["consecutive_failures"],0);self.assertIsNone(s["reason"])
    def test_failure_increments_exactly_once_below_threshold(self):
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=ReleaseRecoveryError("x")):
            with self.assertRaises(SafetyStateError):self.call(3)
        s=read_safety_state(self.root);self.assertEqual((s["generation"],s["consecutive_failures"],s["mode"]),(1,1,"NORMAL"))
    def test_threshold_latches_safe_mode(self):
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=ReleaseRecoveryError("x")):
            for _ in range(2):
                with self.assertRaises(SafetyStateError):self.call(3)
            r=self.call(3)
        self.assertEqual(r["action"],"ENTERED_SAFE_MODE");self.assertEqual(r["safety"]["consecutive_failures"],3);self.assertEqual(r["safety"]["reason"],"RECOVERY_FAILURE_LIMIT")
    def test_safe_mode_blocks_reconcile_and_is_idempotent(self):
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=ReleaseRecoveryError("x")):
            self.call(1)
        before=read_safety_state(self.root)
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=AssertionError("must not run")):
            r=self.call(1)
        self.assertEqual(r["action"],"HOLD_SAFE_MODE");self.assertEqual(read_safety_state(self.root),before)
    def test_success_resets_nonzero_counter_in_normal_mode(self):
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=ReleaseRecoveryError("x")):
            with self.assertRaises(SafetyStateError):self.call(3)
        with mock.patch("kk_f.safety_state.reconcile_release",return_value={"action":"NO_ACTION"}):r=self.call(3)
        self.assertEqual(r["safety"]["consecutive_failures"],0);self.assertEqual(r["safety"]["mode"],"NORMAL");self.assertEqual(r["safety"]["generation"],2)
    def test_zero_counter_success_is_no_write(self):
        before=read_safety_state(self.root)
        with mock.patch("kk_f.safety_state.reconcile_release",return_value={"action":"NO_ACTION"}):r=self.call()
        self.assertEqual(r["safety"],before)
    def test_safe_mode_never_auto_clears(self):
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=ReleaseRecoveryError("x")):self.call(1)
        with mock.patch("kk_f.safety_state.reconcile_release",return_value={"action":"NO_ACTION"}) as m:r=self.call(1)
        self.assertEqual(r["action"],"HOLD_SAFE_MODE");m.assert_not_called()
    def test_clear_requires_exact_generation_and_literal_ack(self):
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=ReleaseRecoveryError("x")):self.call(1)
        g=read_safety_state(self.root)["generation"]
        for gen,ack in ((g-1,True),(g,1),(True,True)):
            with self.assertRaises(SafetyStateError):clear_safe_mode(self.root,expected_generation=gen,acknowledge=ack)
        s=clear_safe_mode(self.root,expected_generation=g,acknowledge=True);self.assertEqual(s["mode"],"NORMAL");self.assertEqual(s["generation"],g+1);self.assertEqual(s["consecutive_failures"],0)
    def test_threshold_type_strict(self):
        for bad in (0,-1,True,1.5,"2"):
            with self.assertRaises(SafetyStateError):self.call(bad)
    def test_corrupt_state_fails_closed_before_reconcile(self):
        (self.root/FILE).write_text("bad")
        with mock.patch("kk_f.safety_state.reconcile_release",side_effect=AssertionError("must not run")):
            with self.assertRaises(SafetyStateError):self.call()
    def test_checksum_tamper_detected(self):
        p=self.root/FILE;v=json.loads(p.read_text());v["consecutive_failures"]=9;p.write_text(json.dumps(v));self.assertRaises(SafetyStateError,read_safety_state,self.root)
if __name__=='__main__':unittest.main()
