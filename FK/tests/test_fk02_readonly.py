from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

for path in ("/root/K/F/src", "/root/K/K/src"):
    if path not in sys.path:
        sys.path.insert(0, path)

from kk_f import fk_gateway
from kk_k.boundary import submit_action
from kk_k.fk_client import submit as fk_submit
from kk_k.kernel import run_once
from kk_k.test_support import project_tempdir
from kk_k.verifier import verify_receipt


def addr(tag):
    return "\0kk-fk02-" + tag + "-" + uuid.uuid4().hex[:10]


def server_once(address, allowed_uid=None):
    ready=threading.Event(); errors=[]
    def target():
        try:
            fk_gateway.serve_once(address=address, allowed_uid=os.getuid() if allowed_uid is None else allowed_uid, ready=ready.set)
        except Exception as exc:
            errors.append(exc); ready.set()
    t=threading.Thread(target=target,daemon=True); t.start()
    if not ready.wait(2): raise AssertionError("gateway not ready")
    if errors: raise errors[0]
    return t,errors


def children():
    p=Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
    return p.read_text().strip() if p.exists() else ""


class FK02ReadonlyTests(unittest.TestCase):
    def test_a01_real_project_state_projection(self):
        a=addr("a01"); t,e=server_once(a)
        before=children()
        r=submit_action("A01_READ_PROJECT_STATE",lambda aid:fk_submit(aid,address=a))
        after=children(); t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt("A01_READ_PROJECT_STATE",r).result,"PASS")
        self.assertEqual(r["evidence"],{"kind":"PROJECT_STATE","status":"ADVERSARIAL_HARDENING_ACCEPTED"})
        self.assertEqual(before,after)

    def test_a02_real_f_status(self):
        a=addr("a02"); t,e=server_once(a)
        r=submit_action("A02_READ_F_STATUS",lambda aid:fk_submit(aid,address=a))
        t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt("A02_READ_F_STATUS",r).result,"PASS")
        self.assertEqual(r["evidence"],{"kind":"F_STATUS","status":"ACCEPTED"})

    def test_k_kernel_real_a02(self):
        a=addr("kernel"); t,e=server_once(a)
        with project_tempdir() as td:
            root=Path(td)
            c=root/"constitution.json"; g=root/"goal.txt"; w=root/"world.txt"
            c.write_text(Path('/root/K/K/K00_CONSTITUTION.json').read_text(encoding='utf-8'),encoding='utf-8')
            g.write_text('read F status',encoding='utf-8'); w.write_text('unknown',encoding='utf-8')
            out=run_once(
                constitution_path=str(c),goal_path=str(g),world_state_path=str(w),
                decision_log_path=str(root/'d.jsonl'),execution_log_path=str(root/'e.jsonl'),
                llm_call=lambda _:'{"schema":"K01.DECISION.1","action_id":"A02_READ_F_STATUS"}',
                f_submit=lambda aid:fk_submit(aid,address=a),
            )
        t.join(2)
        self.assertEqual(e,[])
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(out["action_id"],"A02_READ_F_STATUS")

    def test_group_world_writable_state_is_vetoed(self):
        original=fk_gateway.F_STATE_PATH
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            p=Path(td)/'state.json'
            p.write_text(json.dumps({"status":"ACCEPTED","current_phase":"X","final_acceptance":"ACCEPTED"}),encoding='utf-8')
            p.chmod(0o666)
            fk_gateway.F_STATE_PATH=str(p)
            try:
                a=addr("mode"); t,e=server_once(a)
                r=fk_submit("A02_READ_F_STATUS",address=a); t.join(2)
            finally:
                fk_gateway.F_STATE_PATH=original
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt("A02_READ_F_STATUS",r).result,"VETO")
        self.assertEqual(r["evidence"]["reason_code"],"F_STATE_INVALID")
        self.assertEqual(r["evidence"]["validation_stage"],"F_STATE")

    def test_symlink_state_is_vetoed(self):
        original=fk_gateway.F_STATE_PATH
        with tempfile.TemporaryDirectory(dir='/root/K/F') as td:
            root=Path(td); target=root/'real.json'; link=root/'link.json'
            target.write_text(json.dumps({"status":"ACCEPTED","current_phase":"X","final_acceptance":"ACCEPTED"}),encoding='utf-8')
            link.symlink_to(target)
            fk_gateway.F_STATE_PATH=str(link)
            try:
                a=addr("symlink"); t,e=server_once(a)
                r=fk_submit("A01_READ_PROJECT_STATE",address=a); t.join(2)
            finally:
                fk_gateway.F_STATE_PATH=original
        self.assertEqual(e,[])
        self.assertEqual(verify_receipt("A01_READ_PROJECT_STATE",r).result,"VETO")
        self.assertEqual(r["evidence"]["reason_code"],"F_STATE_INVALID")


if __name__=='__main__': unittest.main()
