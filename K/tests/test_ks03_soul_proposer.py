import json
import inspect
import unittest
from pathlib import Path

import kk_k.soul_proposer as soul_proposer_module
from kk_k.governance import load_policy
from kk_k.loop import run_bounded_loop
from kk_k.memory import verify_event_log
from kk_k.soul_proposer import SoulProposer, SoulProviders
from kk_k.test_support import project_tempdir


def a(action):
    return json.dumps({
        "schema":"KS01.SOUL_A.1","assessment":"a","confidence":"HIGH",
        "candidate_actions":[action,"A05_NO_ACTION"] if action != "A05_NO_ACTION" else [action],
    })


def b(blocked=None):
    return json.dumps({
        "schema":"KS01.SOUL_B.1","assessment":"b","confidence":"HIGH",
        "blocked_actions":blocked or [],
    })


def c(action):
    return json.dumps({
        "schema":"KS01.SOUL_C.1","assessment":"c","confidence":"HIGH",
        "selected_action_id":action,
    })


def evidence(action, stance="SUPPORT"):
    return [{
        "schema":"KS02.EVIDENCE.1","evidence_id":"e1","source_id":"test.source",
        "trust":"UNTRUSTED_EVIDENCE","freshness":"FRESH","stance":stance,
        "actions":[action],"claim":"bounded evidence",
    }]


class KS03SoulProposerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=project_tempdir()
        self.root=Path(self.tmp.name)
        self.audit=str(self.root/"soul-events.jsonl")
        self.policy=load_policy("/root/K/K/K06_POLICY.json")

    def tearDown(self):
        self.tmp.cleanup()

    def proposer(self, action, *, blocked=None, stance="SUPPORT"):
        return SoulProposer(
            providers=SoulProviders(
                soul_a=lambda _:a(action),
                soul_b=lambda _:b(blocked),
                soul_c=lambda _:c(action),
            ),
            context_provider=lambda cycle:f"cycle={cycle}",
            evidence_provider=lambda _: evidence(action,stance),
            audit_log_path=self.audit,
            event_prefix="ks03",
        )

    def test_safe_action_flows_into_k08_executor(self):
        seen=[]
        r=run_bounded_loop(
            policy=self.policy,
            proposer=self.proposer("A02_READ_F_STATUS"),
            executor=lambda action: seen.append(action) or {"action_id":action,"mechanical_verdict":"PASS"},
            log_path=str(self.root/"loop.jsonl"),
            max_cycles=1,
        )
        self.assertEqual((r["status"],seen),("MAX_CYCLES",["A02_READ_F_STATUS"]))
        self.assertEqual(len(verify_event_log(self.audit)),1)

    def test_critic_block_falls_back_to_no_action(self):
        seen=[]
        r=run_bounded_loop(
            policy=self.policy,
            proposer=self.proposer("A02_READ_F_STATUS",blocked=["A02_READ_F_STATUS"]),
            executor=lambda action: seen.append(action) or {"action_id":action,"mechanical_verdict":"PASS"},
            log_path=str(self.root/"loop.jsonl"),max_cycles=8,
        )
        self.assertEqual((r["status"],seen),("NO_ACTION",["A05_NO_ACTION"]))

    def test_fresh_contradiction_falls_back_to_no_action(self):
        seen=[]
        r=run_bounded_loop(
            policy=self.policy,proposer=self.proposer("A02_READ_F_STATUS",stance="CONTRADICT"),
            executor=lambda action: seen.append(action) or {"action_id":action,"mechanical_verdict":"PASS"},
            log_path=str(self.root/"loop.jsonl"),max_cycles=8,
        )
        self.assertEqual((r["status"],seen),("NO_ACTION",["A05_NO_ACTION"]))

    def test_a03_is_stopped_by_k06_before_executor(self):
        seen=[]
        r=run_bounded_loop(
            policy=self.policy,proposer=self.proposer("A03_RUN_F_SMOKE_TEST"),
            executor=lambda action: seen.append(action) or {"action_id":action,"mechanical_verdict":"PASS"},
            log_path=str(self.root/"loop.jsonl"),max_cycles=8,
        )
        self.assertEqual(r["status"],"REQUIRE_HUMAN")
        self.assertEqual(seen,[])

    def test_malformed_soul_output_becomes_proposer_error(self):
        proposer=SoulProposer(
            providers=SoulProviders(soul_a=lambda _:"{}",soul_b=lambda _:b(),soul_c=lambda _:c("A05_NO_ACTION")),
            context_provider=lambda _:"x",evidence_provider=lambda _:[],
            audit_log_path=self.audit,event_prefix="bad",
        )
        seen=[]
        r=run_bounded_loop(
            policy=self.policy,proposer=proposer,
            executor=lambda action: seen.append(action),
            log_path=str(self.root/"loop.jsonl"),max_cycles=8,
        )
        self.assertEqual(r["status"],"PROPOSER_ERROR")
        self.assertEqual(seen,[])

    def test_soul_proposer_has_no_fk_transport_import(self):
        source=inspect.getsource(soul_proposer_module)
        self.assertNotIn("fk_client",source)
        self.assertNotIn("submit(",source)
        self.assertNotIn("execute_governed",source)
