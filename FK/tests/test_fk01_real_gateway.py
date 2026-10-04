from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import unittest
import uuid

F_SRC = "/root/K/F/src"
K_SRC = "/root/K/K/src"
for path in (F_SRC, K_SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from kk_f import fk_gateway
from kk_k.boundary import submit_action
from kk_k.fk_client import FKClientError, submit as fk_submit
from kk_k.kernel import run_once
from kk_k.test_support import project_tempdir
from kk_k.verifier import verify_receipt


def address(tag: str) -> str:
    return "\0kk-fk-test-" + tag + "-" + uuid.uuid4().hex[:12]


def start_once(addr: str, allowed_uid: int):
    ready = threading.Event()
    errors = []
    def target():
        try:
            fk_gateway.serve_once(address=addr, allowed_uid=allowed_uid, ready=ready.set)
        except Exception as exc:
            errors.append(exc)
            ready.set()
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    if not ready.wait(2):
        raise AssertionError("gateway did not become ready")
    if errors:
        raise errors[0]
    return thread, errors


def children() -> str:
    p = Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
    return p.read_text().strip() if p.exists() else ""


def raw_roundtrip(addr: str, raw: bytes) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(addr)
        sock.sendall(raw)
        data = bytearray()
        while not data.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
        return json.loads(bytes(data).decode("utf-8"))
    finally:
        sock.close()


class FK01RealGatewayTests(unittest.TestCase):
    def test_real_k_boundary_to_f_a05_and_verifier(self):
        addr = address("a05")
        thread, errors = start_once(addr, os.getuid())
        before = children()
        receipt = submit_action("A05_NO_ACTION", lambda aid: fk_submit(aid, address=addr))
        after = children()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(receipt["schema"], "FK01.F_RECEIPT.1")
        self.assertEqual(verify_receipt("A05_NO_ACTION", receipt).result, "PASS")
        self.assertEqual(before, after)
        self.assertFalse(receipt["evidence"]["process_started"])

    def test_real_k_kernel_one_shot_uses_real_f_gateway(self):
        addr = address("kernel")
        thread, errors = start_once(addr, os.getuid())
        with project_tempdir() as td:
            root = Path(td)
            constitution = root / "constitution.json"
            goal = root / "goal.txt"
            world = root / "world.txt"
            dlog = root / "decision.jsonl"
            elog = root / "execution.jsonl"
            constitution.write_text(Path("/root/K/K/K00_CONSTITUTION.json").read_text(encoding="utf-8"), encoding="utf-8")
            goal.write_text("test real FK A05", encoding="utf-8")
            world.write_text("F real gateway available", encoding="utf-8")
            result = run_once(
                constitution_path=str(constitution),
                goal_path=str(goal),
                world_state_path=str(world),
                decision_log_path=str(dlog),
                execution_log_path=str(elog),
                llm_call=lambda _prompt: '{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}',
                f_submit=lambda aid: fk_submit(aid, address=addr),
            )
        thread.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["action_id"], "A05_NO_ACTION")

    def test_a03_without_human_approval_returns_typed_veto(self):
        addr = address("human-required")
        thread, errors = start_once(addr, os.getuid())
        receipt = fk_submit("A03_RUN_F_SMOKE_TEST", address=addr)
        thread.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(verify_receipt("A03_RUN_F_SMOKE_TEST", receipt).result, "VETO")
        self.assertEqual(receipt["evidence"]["reason_code"], "HUMAN_APPROVAL_REQUIRED")
        self.assertEqual(receipt["evidence"]["validation_stage"], "HUMAN_APPROVAL")

    def test_wrong_peer_uid_returns_typed_veto(self):
        addr = address("peer")
        wrong_uid = os.getuid() + 1
        thread, errors = start_once(addr, wrong_uid)
        receipt = fk_submit("A05_NO_ACTION", address=addr)
        thread.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(verify_receipt("A05_NO_ACTION", receipt).result, "VETO")
        self.assertEqual(receipt["evidence"]["reason_code"], "PEER_AUTH_DENY")
        self.assertEqual(receipt["evidence"]["validation_stage"], "PEER_AUTH")

    def test_extra_field_fails_closed(self):
        addr = address("extra")
        thread, errors = start_once(addr, os.getuid())
        value = {"schema":"FK01.REQUEST.1","action_id":"A05_NO_ACTION","params":{}}
        response = raw_roundtrip(addr, (json.dumps(value,separators=(",",":"))+"\n").encode())
        thread.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(response, {"schema":"FK01.ERROR.1","reason_code":"INVALID_REQUEST","stage":"REQUEST_PARSE"})

    def test_duplicate_key_fails_closed(self):
        addr = address("dup")
        thread, errors = start_once(addr, os.getuid())
        raw = b'{"schema":"FK01.REQUEST.1","action_id":"A05_NO_ACTION","action_id":"A05_NO_ACTION"}\n'
        response = raw_roundtrip(addr, raw)
        thread.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(response["reason_code"], "INVALID_REQUEST")
        self.assertEqual(response["stage"], "REQUEST_PARSE")

    def test_unknown_action_fails_closed(self):
        addr = address("unknown")
        thread, errors = start_once(addr, os.getuid())
        raw = b'{"schema":"FK01.REQUEST.1","action_id":"RUN_SHELL"}\n'
        response = raw_roundtrip(addr, raw)
        thread.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(response["reason_code"], "INVALID_REQUEST")

    def test_non_abstract_client_address_rejected(self):
        with self.assertRaises(FKClientError):
            fk_submit("A05_NO_ACTION", address="/tmp/not-allowed.sock")

    def test_gateway_has_no_subprocess_dependency(self):
        source = Path("/root/K/F/src/kk_f/fk_gateway.py").read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.", source)
        self.assertIn("socket.AF_UNIX", source)
        self.assertNotIn("socket.AF_INET", source)


if __name__ == "__main__":
    unittest.main()
