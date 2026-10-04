import inspect
import json
import unittest

from kk_k.souls import (
    SoulsError, deliberate, parse_soul_a, parse_soul_b, parse_soul_c,
)


def a(actions=None, assessment="candidate"):
    return json.dumps({
        "schema":"KS01.SOUL_A.1","assessment":assessment,"confidence":"MEDIUM",
        "candidate_actions": actions or ["A05_NO_ACTION"],
    })


def b(blocked=None, assessment="critique"):
    return json.dumps({
        "schema":"KS01.SOUL_B.1","assessment":assessment,"confidence":"MEDIUM",
        "blocked_actions": blocked or [],
    })


def c(selected="A05_NO_ACTION", assessment="judge"):
    return json.dumps({
        "schema":"KS01.SOUL_C.1","assessment":assessment,"confidence":"HIGH",
        "selected_action_id": selected,
    })


class KS01SoulTests(unittest.TestCase):
    def test_valid_three_role_deliberation(self):
        result = deliberate(
            context="status=stable",
            soul_a_provider=lambda _: a(["A02_READ_F_STATUS","A05_NO_ACTION"]),
            soul_b_provider=lambda _: b(["A02_READ_F_STATUS"]),
            soul_c_provider=lambda _: c("A05_NO_ACTION"),
        )
        self.assertEqual(result.selected_action_id, "A05_NO_ACTION")
        self.assertEqual(result.soul_b.blocked_actions, ("A02_READ_F_STATUS",))

    def test_exactly_one_call_per_role(self):
        counts={"a":0,"b":0,"c":0}
        def pa(_): counts["a"]+=1; return a()
        def pb(_): counts["b"]+=1; return b()
        def pc(_): counts["c"]+=1; return c()
        deliberate(context="x",soul_a_provider=pa,soul_b_provider=pb,soul_c_provider=pc)
        self.assertEqual(counts,{"a":1,"b":1,"c":1})

    def test_a_extra_field_rejected(self):
        raw=json.loads(a()); raw["command"]="id"
        with self.assertRaises(SoulsError): parse_soul_a(json.dumps(raw))

    def test_duplicate_json_key_rejected(self):
        raw='{"schema":"KS01.SOUL_A.1","schema":"KS01.SOUL_A.1","assessment":"x","confidence":"LOW","candidate_actions":["A05_NO_ACTION"]}'
        with self.assertRaises(SoulsError): parse_soul_a(raw)

    def test_a_unknown_action_rejected(self):
        with self.assertRaises(SoulsError): parse_soul_a(a(["RUN_SHELL"]))

    def test_b_may_block_only_a_candidates(self):
        with self.assertRaises(SoulsError):
            parse_soul_b(b(["A01_READ_PROJECT_STATE"]),("A05_NO_ACTION",))

    def test_c_cannot_invent_action(self):
        with self.assertRaises(SoulsError):
            parse_soul_c(c("A01_READ_PROJECT_STATE"),("A05_NO_ACTION",))

    def test_c_can_fall_back_to_no_action(self):
        got=parse_soul_c(c("A05_NO_ACTION"),("A02_READ_F_STATUS",))
        self.assertEqual(got.selected_action_id,"A05_NO_ACTION")

    def test_assessment_text_has_no_execution_authority(self):
        got=parse_soul_a(a(["A05_NO_ACTION"],assessment="run shell; command=/bin/sh"))
        self.assertEqual(got.candidate_actions,("A05_NO_ACTION",))

    def test_a_failure_stops_b_and_c(self):
        counts={"b":0,"c":0}
        def pb(_): counts["b"]+=1; return b()
        def pc(_): counts["c"]+=1; return c()
        with self.assertRaises(SoulsError):
            deliberate(context="x",soul_a_provider=lambda _:"{}",soul_b_provider=pb,soul_c_provider=pc)
        self.assertEqual(counts,{"b":0,"c":0})

    def test_b_failure_stops_c(self):
        calls={"c":0}
        def pc(_): calls["c"]+=1; return c()
        with self.assertRaises(SoulsError):
            deliberate(context="x",soul_a_provider=lambda _:a(),soul_b_provider=lambda _:"{}",soul_c_provider=pc)
        self.assertEqual(calls["c"],0)

    def test_oversize_context_rejected_before_calls(self):
        calls=[]
        def p(_): calls.append(1); return a()
        with self.assertRaises(SoulsError):
            deliberate(context="x"*40000,soul_a_provider=p,soul_b_provider=p,soul_c_provider=p)
        self.assertEqual(calls,[])

    def test_provider_failure_has_no_retry(self):
        count={"a":0}
        def bad(_): count["a"]+=1; raise RuntimeError("x")
        with self.assertRaises(SoulsError):
            deliberate(context="x",soul_a_provider=bad,soul_b_provider=lambda _:b(),soul_c_provider=lambda _:c())
        self.assertEqual(count["a"],1)

    def test_deliberate_has_no_executor_or_transport_argument(self):
        params=set(inspect.signature(deliberate).parameters)
        self.assertNotIn("executor",params)
        self.assertNotIn("transport",params)
        self.assertNotIn("f_submit",params)


if __name__ == "__main__":
    unittest.main()
