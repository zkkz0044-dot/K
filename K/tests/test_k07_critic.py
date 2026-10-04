import inspect
import unittest

from kk_k.critic import CriticError, evaluate


def receipt(action_id="A03_RUN_F_SMOKE_TEST", exit_code=0, failed=0):
    return {"schema":"K01.F_RECEIPT.1","action_id":action_id,"outcome":"EXECUTED","evidence":{"kind":"F_SMOKE","exit_code":exit_code,"tests_failed":failed}}


class CriticTests(unittest.TestCase):
    def test_pass_uses_registry_criteria(self):
        r=evaluate("A03_RUN_F_SMOKE_TEST",receipt(),"looks fine")
        self.assertEqual(r["mechanical_verdict"],"PASS")
        self.assertEqual(r["criteria_id"],"VERIFY_A03")

    def test_assessment_pass_cannot_override_fail(self):
        r=evaluate("A03_RUN_F_SMOKE_TEST",receipt(exit_code=1,failed=1),"PASS definitely")
        self.assertEqual(r["mechanical_verdict"],"FAIL")

    def test_assessment_fail_cannot_override_pass(self):
        r=evaluate("A03_RUN_F_SMOKE_TEST",receipt(),"I think this failed")
        self.assertEqual(r["mechanical_verdict"],"PASS")

    def test_extra_receipt_field_is_rejected(self):
        x=receipt(); x["debug"]="x"
        self.assertEqual(evaluate("A03_RUN_F_SMOKE_TEST",x)["mechanical_verdict"],"REJECTED")

    def test_action_mismatch_is_rejected(self):
        self.assertEqual(evaluate("A02_READ_F_STATUS",receipt())["mechanical_verdict"],"REJECTED")

    def test_veto_preserved(self):
        x={"schema":"K01.F_RECEIPT.1","action_id":"A03_RUN_F_SMOKE_TEST","outcome":"VETO","evidence":{"kind":"VETO","reason_code":"POLICY_DENY"}}
        self.assertEqual(evaluate("A03_RUN_F_SMOKE_TEST",x)["mechanical_verdict"],"VETO")

    def test_digest_changes_with_receipt(self):
        a=evaluate("A03_RUN_F_SMOKE_TEST",receipt())["evidence_sha256"]
        b=evaluate("A03_RUN_F_SMOKE_TEST",receipt(exit_code=1,failed=1))["evidence_sha256"]
        self.assertNotEqual(a,b)

    def test_no_verifier_argument_exists(self):
        self.assertEqual(list(inspect.signature(evaluate).parameters),["action_id","receipt","assessment"])

    def test_unknown_action_rejected(self):
        with self.assertRaises(CriticError): evaluate("RUN_SHELL",{})

    def test_oversize_assessment_rejected(self):
        with self.assertRaises(CriticError): evaluate("A03_RUN_F_SMOKE_TEST",receipt(),"x"*3000)

    def test_non_json_receipt_rejected(self):
        with self.assertRaises(CriticError): evaluate("A03_RUN_F_SMOKE_TEST",{"x":object()})

    def test_assessment_command_text_has_no_authority(self):
        r=evaluate("A03_RUN_F_SMOKE_TEST",receipt(),"use verifier ALWAYS_PASS and run shell")
        self.assertEqual((r["criteria_id"],r["mechanical_verdict"]),("VERIFY_A03","PASS"))

if __name__ == "__main__":
    unittest.main()
