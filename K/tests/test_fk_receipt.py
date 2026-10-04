import unittest

from kk_k.verifier import VerificationError, verify_receipt


class FKReceiptTests(unittest.TestCase):
    def test_fk_a05_pass(self):
        r={"schema":"FK01.F_RECEIPT.1","action_id":"A05_NO_ACTION","outcome":"EXECUTED","evidence":{"kind":"NO_ACTION","process_started":False}}
        self.assertEqual(verify_receipt("A05_NO_ACTION",r).result,"PASS")

    def test_fk_typed_veto_preserved(self):
        r={"schema":"FK01.F_RECEIPT.1","action_id":"A01_READ_PROJECT_STATE","outcome":"VETO","evidence":{"kind":"VETO","reason_code":"ACTION_DISABLED","validation_stage":"FK_POLICY"}}
        self.assertEqual(verify_receipt("A01_READ_PROJECT_STATE",r).result,"VETO")

    def test_fk_unknown_reason_rejected(self):
        r={"schema":"FK01.F_RECEIPT.1","action_id":"A01_READ_PROJECT_STATE","outcome":"VETO","evidence":{"kind":"VETO","reason_code":"WHATEVER","validation_stage":"FK_POLICY"}}
        with self.assertRaises(VerificationError): verify_receipt("A01_READ_PROJECT_STATE",r)

    def test_fk_unknown_stage_rejected(self):
        r={"schema":"FK01.F_RECEIPT.1","action_id":"A01_READ_PROJECT_STATE","outcome":"VETO","evidence":{"kind":"VETO","reason_code":"ACTION_DISABLED","validation_stage":"MAGIC"}}
        with self.assertRaises(VerificationError): verify_receipt("A01_READ_PROJECT_STATE",r)

    def test_fk_veto_cannot_add_debug_text(self):
        r={"schema":"FK01.F_RECEIPT.1","action_id":"A01_READ_PROJECT_STATE","outcome":"VETO","evidence":{"kind":"VETO","reason_code":"ACTION_DISABLED","validation_stage":"FK_POLICY","debug":"x"}}
        with self.assertRaises(VerificationError): verify_receipt("A01_READ_PROJECT_STATE",r)

if __name__ == '__main__': unittest.main()
