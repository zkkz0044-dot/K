from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

for p in ("/root/K/F/src", "/root/K/K/src"):
    if p not in sys.path:
        sys.path.insert(0, p)

from kk_f.tool_file_read import FileReadError, read_project_file

SEARCH_PATH = "/root/K/F/capabilities/search_worker.py"
spec = importlib.util.spec_from_file_location("kk_search_worker_test", SEARCH_PATH)
search_worker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(search_worker)


class FakePeerSocket:
    def __init__(self, pid: int, uid: int):
        self.pid = pid
        self.uid = uid

    def getsockopt(self, level, option, size):
        return struct.pack("3i", self.pid, self.uid, 1000)


class FKP06CapabilityIsolationTests(unittest.TestCase):
    def test_file_read_allows_k_owned_text(self):
        out = read_project_file("/root/K/K/PROJECT_STATE.json")
        self.assertEqual(out["schema"], "F.TOOL.FILE_READ.1")
        self.assertTrue(out["path"].startswith("/root/K/K/"))

    def test_file_read_denies_f_and_fk(self):
        for path in ("/root/K/F/PROJECT_STATE.json", "/root/K/FK/state/a03_approval.json"):
            with self.assertRaises(FileReadError):
                read_project_file(path)

    def test_file_read_denies_sensitive_k_subtrees(self):
        for path in (
            "/root/K/K/runtime/example.txt",
            "/root/K/K/state/example.txt",
            "/root/K/K/models/example.txt",
            "/root/K/K/vendor/example.txt",
        ):
            with self.assertRaises(FileReadError):
                read_project_file(path)

    def test_search_worker_accepts_only_exact_f_gateway_cgroup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pid = 4242
            proc = root / str(pid)
            proc.mkdir(parents=True)
            (proc / "cgroup").write_text(
                "0::/system.slice/kk-fk-tool-gateway.service\n",
                encoding="utf-8",
            )
            self.assertTrue(search_worker.peer_authorized(FakePeerSocket(pid, 0), root))
            self.assertFalse(search_worker.peer_authorized(FakePeerSocket(pid, 1001), root))
            (proc / "cgroup").write_text(
                "0::/system.slice/kk-k-runtime.service\n",
                encoding="utf-8",
            )
            self.assertFalse(search_worker.peer_authorized(FakePeerSocket(pid, 0), root))

    def test_search_request_is_exact_and_bounded(self):
        good = json.dumps({"schema": "KK.CAP.SEARCH.1", "query": "example"}).encode()
        self.assertEqual(search_worker.strict(good)["query"], "example")
        bad = json.dumps({"schema": "KK.CAP.SEARCH.1", "query": "example", "url": "x"}).encode()
        with self.assertRaises(ValueError):
            search_worker.strict(bad)


if __name__ == "__main__":
    unittest.main()

class SearchFreshnessRoutingTests(unittest.TestCase):
    def test_fresh_marker_selection_contract(self):
        self.assertIn('today', search_worker.FRESH_MARKERS)
        self.assertIn('最新', search_worker.FRESH_MARKERS)
