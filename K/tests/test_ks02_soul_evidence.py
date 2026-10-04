import json
import unittest
from pathlib import Path

from kk_k.soul_evidence import (
    SoulEvidenceError, append_soul_audit, gate_soul_decision, validate_evidence,
)
from kk_k.souls import SoulAResult, SoulBResult, SoulCResult, SoulDecision
from kk_k.test_support import project_tempdir
from kk_k.memory import verify_event_log


def decision(selected="A02_READ_F_STATUS", blocked=()):
    a=SoulAResult("PRIVATE_A_TEXT","HIGH",("A02_READ_F_STATUS","A05_NO_ACTION"))
    b=SoulBResult("PRIVATE_B_TEXT","MEDIUM",tuple(blocked))
    c=SoulCResult("PRIVATE_C_TEXT","HIGH",selected)
    return SoulDecision(selected,a,b,c)


def evidence(eid="e1", freshness="FRESH", stance="SUPPORT", actions=None, claim="PRIVATE_EVIDENCE_TEXT"):
    return {
        "schema":"KS02.EVIDENCE.1","evidence_id":eid,"source_id":"source.1",
        "trust":"UNTRUSTED_EVIDENCE","freshness":freshness,"stance":stance,
        "actions":actions or ["A02_READ_F_STATUS"],"claim":claim,
    }


class KS02EvidenceTests(unittest.TestCase):
    def test_no_action_needs_no_external_evidence(self):
        r=gate_soul_decision(decision("A05_NO_ACTION"),[])
        self.assertEqual((r.outcome,r.governed_candidate_id),("NO_ACTION","A05_NO_ACTION"))

    def test_critic_block_forces_safe_fallback(self):
        r=gate_soul_decision(decision(blocked=("A02_READ_F_STATUS",)),[evidence()])
        self.assertEqual((r.reason,r.governed_candidate_id),("CRITIC_BLOCK","A05_NO_ACTION"))

    def test_no_evidence_forces_safe_fallback(self):
        r=gate_soul_decision(decision(),[])
        self.assertEqual(r.reason,"NO_FRESH_SUPPORT")

    def test_stale_support_is_not_sufficient(self):
        r=gate_soul_decision(decision(),[evidence(freshness="STALE")])
        self.assertEqual(r.governed_candidate_id,"A05_NO_ACTION")

    def test_fresh_support_allows_candidate(self):
        r=gate_soul_decision(decision(),[evidence()])
        self.assertEqual((r.outcome,r.governed_candidate_id),("APPROVE_CANDIDATE","A02_READ_F_STATUS"))

    def test_fresh_contradiction_overrides_support(self):
        items=[evidence("e1"),evidence("e2",stance="CONTRADICT")]
        r=gate_soul_decision(decision(),items)
        self.assertEqual((r.reason,r.governed_candidate_id),("FRESH_CONTRADICTION","A05_NO_ACTION"))

    def test_trust_escalation_is_rejected(self):
        item=evidence(); item["trust"]="TRUSTED"
        with self.assertRaises(SoulEvidenceError): validate_evidence([item])

    def test_extra_evidence_field_rejected(self):
        item=evidence(); item["command"]="id"
        with self.assertRaises(SoulEvidenceError): validate_evidence([item])

    def test_duplicate_evidence_id_rejected(self):
        with self.assertRaises(SoulEvidenceError):
            validate_evidence([evidence("e1"),evidence("e1",stance="CONTRADICT")])

    def test_unknown_action_in_evidence_rejected(self):
        with self.assertRaises(SoulEvidenceError):
            validate_evidence([evidence(actions=["RUN_SHELL"])])

    def test_audit_records_digests_not_private_text(self):
        with project_tempdir() as td:
            path=Path(td)/"events.jsonl"
            r=gate_soul_decision(decision(),[evidence()])
            append_soul_audit(str(path),"soul-e1",r)
            records=verify_event_log(str(path))
            self.assertEqual(len(records),1)
            raw=path.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_A_TEXT",raw)
            self.assertNotIn("PRIVATE_B_TEXT",raw)
            self.assertNotIn("PRIVATE_C_TEXT",raw)
            self.assertNotIn("PRIVATE_EVIDENCE_TEXT",raw)
            summary=json.loads(records[0]["summary"])
            self.assertEqual(summary["governed_candidate_id"],"A02_READ_F_STATUS")


if __name__ == "__main__":
    unittest.main()
