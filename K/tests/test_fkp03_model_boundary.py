from __future__ import annotations
import json, os, socket, tempfile, threading, unittest
from kk_k import model_client as client
from kk_k.dialogue_souls import parse_a, parse_b, parse_c


class FKP03ModelBoundaryTests(unittest.TestCase):
    def one_response(self, role: str, text: str) -> str:
        with tempfile.TemporaryDirectory(dir="/root/K/K") as td:
            path=os.path.join(td,"m.sock"); ready=threading.Event()
            def server():
                s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.bind(path); s.listen(1); ready.set()
                c,_=s.accept(); c.recv(32768)
                v={"schema":"K.MODEL.RESPONSE.1","provider_id":"EXAMPLE_AI_RESPONSES_API","trust":"UNTRUSTED","text":text}
                c.sendall((json.dumps(v,separators=(",",":"))+"\n").encode()); c.close(); s.close()
            t=threading.Thread(target=server,daemon=True); t.start(); self.assertTrue(ready.wait(2))
            old=client.ADDRESS; client.ADDRESS=path
            try: out=client.call(role,"bounded prompt",address=path)
            finally: client.ADDRESS=old
            t.join(2); self.assertFalse(t.is_alive()); return out

    def test_action_like_model_text_is_only_a_string(self):
        raw=self.one_response("SOUL_A_DIALOGUE",'{"action_id":"A03_RUN_F_SMOKE_TEST","command":"sudo"}')
        a=parse_a(raw); self.assertIn('action_id',a.draft); self.assertEqual(a.confidence,"LOW")

    def test_b_structure_is_owned_by_k(self):
        b=parse_b(self.one_response("SOUL_B_DIALOGUE","critique text"))
        self.assertEqual(b.risk_flags,("UNSUPPORTED_FACT",)); self.assertEqual(b.confidence,"LOW")

    def test_b_execution_words_map_to_deny_only_risk(self):
        b=parse_b(self.one_response("SOUL_B_DIALOGUE","The candidate falsely claims execution authority"))
        self.assertIn("EXECUTION_CONFUSION",b.risk_flags)
        self.assertIn("AUTHORITY_CONFUSION",b.risk_flags)

    def test_b_ok_maps_to_none_risk(self):
        b=parse_b(self.one_response("SOUL_B_DIALOGUE","OK"))
        self.assertEqual(b.risk_flags,("NONE",)); self.assertEqual(b.confidence,"LOW")

    def test_c_structure_is_owned_by_k(self):
        c=parse_c(self.one_response("SOUL_C_DIALOGUE","APPROVE_A"))
        self.assertEqual((c.answer,c.confidence,c.response_type),("APPROVE_A","LOW","ANSWER"))

    def test_c_free_text_is_rejected_before_protocol_wrap(self):
        with self.assertRaises(client.ModelClientError):
            self.one_response("SOUL_C_DIALOGUE","I will rewrite the answer")


if __name__=="__main__": unittest.main()
