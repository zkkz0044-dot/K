import unittest

from kk_k.verifier import VerificationError, verify_receipt


def receipt(action_id, evidence, outcome="EXECUTED"):
    return {
        "schema": "K01.F_RECEIPT.1",
        "action_id": action_id,
        "outcome": outcome,
        "evidence": evidence,
    }


class VerifierTests(unittest.TestCase):
    def test_a01(self):
        r = receipt("A01_READ_PROJECT_STATE", {"kind": "PROJECT_STATE", "status": "ADVERSARIAL_HARDENING_ACCEPTED"})
        self.assertEqual(verify_receipt("A01_READ_PROJECT_STATE", r).result, "PASS")

    def test_a02(self):
        r = receipt("A02_READ_F_STATUS", {"kind": "F_STATUS", "status": "ACCEPTED"})
        self.assertEqual(verify_receipt("A02_READ_F_STATUS", r).result, "PASS")

    def test_a03_pass_and_fail(self):
        good = receipt("A03_RUN_F_SMOKE_TEST", {"kind": "F_SMOKE", "exit_code": 0, "tests_failed": 0})
        bad = receipt("A03_RUN_F_SMOKE_TEST", {"kind": "F_SMOKE", "exit_code": 1, "tests_failed": 1})
        self.assertEqual(verify_receipt("A03_RUN_F_SMOKE_TEST", good).result, "PASS")
        self.assertEqual(verify_receipt("A03_RUN_F_SMOKE_TEST", bad).result, "FAIL")

    def test_a04(self):
        r = receipt("A04_WRITE_K_DECISION_LOG", {"kind": "K_DECISION_LOG", "appended": True, "durable": True})
        self.assertEqual(verify_receipt("A04_WRITE_K_DECISION_LOG", r).result, "PASS")

    def test_a05(self):
        r = receipt("A05_NO_ACTION", {"kind": "NO_ACTION", "process_started": False})
        self.assertEqual(verify_receipt("A05_NO_ACTION", r).result, "PASS")

    def test_veto(self):
        r = receipt("A03_RUN_F_SMOKE_TEST", {"kind": "VETO", "reason_code": "POLICY_DENY"}, outcome="VETO")
        self.assertEqual(verify_receipt("A03_RUN_F_SMOKE_TEST", r).result, "VETO")

    def test_rejects_extra_receipt_field(self):
        r = receipt("A05_NO_ACTION", {"kind": "NO_ACTION", "process_started": False})
        r["debug"] = "x"
        with self.assertRaises(VerificationError):
            verify_receipt("A05_NO_ACTION", r)

    def test_rejects_action_mismatch(self):
        r = receipt("A05_NO_ACTION", {"kind": "NO_ACTION", "process_started": False})
        with self.assertRaises(VerificationError):
            verify_receipt("A02_READ_F_STATUS", r)


if __name__ == "__main__":
    unittest.main()
