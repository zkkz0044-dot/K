import json
import os
import threading
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_gateway

from kk_k.fk_client import submit
from kk_k.governance import load_policy
from kk_k.loop import run_bounded_loop
from kk_k.soul_proposer import SoulProposer, SoulProviders
from kk_k.test_support import project_tempdir
from kk_k.verifier import verify_receipt


def soul_json(role, action):
    if role == "a":
        return json.dumps({"schema":"KS01.SOUL_A.1","assessment":"a","confidence":"HIGH","candidate_actions":[action,"A05_NO_ACTION"]})
    if role == "b":
        return json.dumps({"schema":"KS01.SOUL_B.1","assessment":"b","confidence":"HIGH","blocked_actions":[]})
    return json.dumps({"schema":"KS01.SOUL_C.1","assessment":"c","confidence":"HIGH","selected_action_id":action})


def evidence(action):
    return [{
        "schema":"KS02.EVIDENCE.1","evidence_id":"live.e1","source_id":"live.fk",
        "trust":"UNTRUSTED_EVIDENCE","freshness":"FRESH","stance":"SUPPORT",
        "actions":[action],"claim":"live FK integration evidence",
    }]


class FKSoulRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=project_tempdir()
        self.root=Path(self.tmp.name)
        self.policy=load_policy("/root/K/K/K06_POLICY.json")

    def tearDown(self):
        self.tmp.cleanup()

    def make_proposer(self, action):
        return SoulProposer(
            providers=SoulProviders(
                soul_a=lambda _:soul_json("a",action),
                soul_b=lambda _:soul_json("b",action),
                soul_c=lambda _:soul_json("c",action),
            ),
            context_provider=lambda cycle:f"live-cycle={cycle}",
            evidence_provider=lambda _:evidence(action),
            audit_log_path=str(self.root/"soul-events.jsonl"),
            event_prefix="livefk",
        )

    def gateway_executor(self, action):
        address="\0kk-fk-soul-"+uuid4().hex[:10]
        ready=threading.Event()
        errors=[]
        def server():
            try:
                fk_gateway.serve_once(address=address,allowed_uid=os.getuid(),ready=ready.set)
            except Exception as exc:
                errors.append(exc)
        thread=threading.Thread(target=server,daemon=True)
        thread.start(); self.assertTrue(ready.wait(2))
        receipt=submit(action,address=address)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[])
        verified=verify_receipt(action,receipt)
        return {"action_id":action,"mechanical_verdict":verified.result}

    def test_three_souls_to_f_gateway_a02(self):
        calls=[]
        def executor(action):
            calls.append(action)
            return self.gateway_executor(action)
        result=run_bounded_loop(
            policy=self.policy,proposer=self.make_proposer("A02_READ_F_STATUS"),
            executor=executor,log_path=str(self.root/"loop.jsonl"),max_cycles=1,
        )
        self.assertEqual(result["status"],"MAX_CYCLES")
        self.assertEqual(calls,["A02_READ_F_STATUS"])

    def test_three_souls_a03_stops_before_live_transport(self):
        calls=[]
        result=run_bounded_loop(
            policy=self.policy,proposer=self.make_proposer("A03_RUN_F_SMOKE_TEST"),
            executor=lambda action:calls.append(action) or self.gateway_executor(action),
            log_path=str(self.root/"loop.jsonl"),max_cycles=8,
        )
        self.assertEqual(result["status"],"REQUIRE_HUMAN")
        self.assertEqual(calls,[])


if __name__ == "__main__":
    unittest.main()
