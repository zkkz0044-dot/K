from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import unittest
import uuid

for p in ("/root/K/F/src", "/root/K/K/src"):
    if p not in sys.path:
        sys.path.insert(0, p)

from kk_f.fk_tool_gateway import (
    ENABLED_TOOLS,
    REQUEST_SCHEMA,
    REQUEST_SCHEMA_V2,
    ALLOWED_TOOL_CLIENT_UNITS,
    REQUEST_SCHEMA_V2,
    dispatch,
    parse_request,
    serve_once,
)
from kk_k.external_tool_client import submit_external_tool


class FKP06ToolGatewayTests(unittest.TestCase):
    def test_exact_approved_tool_surface(self):
        self.assertEqual(ENABLED_TOOLS, frozenset({"remote.vps.health", "files.read", "browser.search"}))

    def test_v1_remote_has_no_payload_or_params(self):
        raw = json.dumps({"schema": REQUEST_SCHEMA, "tool": "remote.vps.health"}).encode()
        self.assertEqual(parse_request(raw)["tool"], "remote.vps.health")
        bad = json.dumps({"schema": REQUEST_SCHEMA, "tool": "remote.vps.health", "extra": "x"}).encode()
        with self.assertRaises(Exception):
            parse_request(bad)

    def test_parameterized_tools_require_v2_exact_args_envelope(self):
        good = json.dumps({"schema": REQUEST_SCHEMA_V2, "tool": "files.read", "args": {"path": "/root/K/README.md"}}).encode()
        self.assertEqual(parse_request(good)["args"]["path"], "/root/K/README.md")
        with self.assertRaises(Exception):
            parse_request(json.dumps({"schema": REQUEST_SCHEMA, "tool": "files.read"}).encode())
        with self.assertRaises(Exception):
            parse_request(json.dumps({"schema": REQUEST_SCHEMA_V2, "tool": "files.read", "args": {"path": "/root/K/README.md"}, "extra": 1}).encode())

    def test_exact_tool_client_identities(self):
        self.assertEqual(ALLOWED_TOOL_CLIENT_UNITS, frozenset({"kk-k-runtime.service", "kk-gpt-tool-runtime.service"}))

    def test_parameterized_surface_is_exact(self):
        good_file = json.dumps({"schema": REQUEST_SCHEMA_V2, "tool": "files.read", "args": {"path": "/root/K/K/PROJECT_STATE.json"}}).encode()
        self.assertEqual(parse_request(good_file)["tool"], "files.read")
        good_search = json.dumps({"schema": REQUEST_SCHEMA_V2, "tool": "browser.search", "args": {"query": "example"}}).encode()
        self.assertEqual(parse_request(good_search)["tool"], "browser.search")
        for bad in (
            {"schema": REQUEST_SCHEMA, "tool": "files.read"},
            {"schema": REQUEST_SCHEMA, "tool": "browser.search"},
            {"schema": REQUEST_SCHEMA_V2, "tool": "remote.vps.health", "args": {}},
            {"schema": REQUEST_SCHEMA_V2, "tool": "files.read", "args": {"path": "x"}, "command": "id"},
        ):
            with self.assertRaises(Exception):
                parse_request(json.dumps(bad).encode())

    def test_files_write_is_rejected_by_active_gateway(self):
        raw=json.dumps({'schema':REQUEST_SCHEMA_V2,'tool':'files.write','args':{'path':'/root/K/K/workspace/x.txt','content':'x'}}).encode()
        with self.assertRaises(Exception):
            parse_request(raw)
        receipt=dispatch('files.write',peer_uid=os.getuid(),allowed_uid=os.getuid(),args={'path':'/root/K/K/workspace/x.txt','content':'x'})
        self.assertEqual(receipt['outcome'],'VETO')
        self.assertEqual(receipt['evidence']['reason_code'],'TOOL_DISABLED')

    def test_peer_auth_denies_wrong_uid(self):
        receipt = dispatch("remote.vps.health", peer_uid=1001, allowed_uid=1002)
        self.assertEqual(receipt["outcome"], "VETO")
        self.assertEqual(receipt["evidence"]["reason_code"], "PEER_AUTH_DENY")

    def test_dispatch_returns_fixed_health_receipt(self):
        receipt = dispatch("remote.vps.health", peer_uid=os.getuid(), allowed_uid=os.getuid())
        self.assertEqual(receipt["outcome"], "EXECUTED")
        self.assertEqual(receipt["evidence"]["kind"], "HOST_HEALTH")
        health = receipt["evidence"]["health"]
        self.assertEqual(health["schema"], "F.TOOL.HOST_HEALTH.1")
        self.assertGreaterEqual(health["cpu_count"], 1)

    def test_live_af_unix_roundtrip_with_k_client(self):
        address = "\0kk-fk-tool-test-" + uuid.uuid4().hex[:12]
        ready = threading.Event()
        errors = []

        def server():
            try:
                serve_once(address=address, allowed_uid=os.getuid(), ready=ready.set)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(2))
        receipt = submit_external_tool("remote.vps.health", address=address, timeout_seconds=2)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(receipt["outcome"], "EXECUTED")
        self.assertEqual(receipt["tool"], "remote.vps.health")

    def test_unknown_tool_is_rejected_at_parse(self):
        raw = json.dumps({"schema": REQUEST_SCHEMA, "tool": "shell.exec"}).encode()
        with self.assertRaises(Exception):
            parse_request(raw)


if __name__ == "__main__":
    unittest.main()
