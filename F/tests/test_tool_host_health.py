from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from kk_f.tool_host_health import SCHEMA, HostHealthError, _read_meminfo, _read_uptime_seconds, collect_host_health


class ToolHostHealthTests(unittest.TestCase):
    def test_live_health_shape(self):
        out = collect_host_health()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertGreaterEqual(out["uptime_seconds"], 0)
        self.assertGreaterEqual(out["cpu_count"], 1)
        self.assertEqual(set(out["load"]), {"one", "five", "fifteen"})
        self.assertGreater(out["memory"]["total_bytes"], 0)
        self.assertGreaterEqual(out["memory"]["available_bytes"], 0)
        self.assertGreater(out["disk_root"]["total_bytes"], 0)

    def test_parser_rejects_missing_meminfo(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "meminfo"
            path.write_text("MemTotal: 100 kB\n", encoding="ascii")
            with self.assertRaises(HostHealthError):
                _read_meminfo(path)

    def test_uptime_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "uptime"
            path.write_text("not-a-number\n", encoding="ascii")
            with self.assertRaises(HostHealthError):
                _read_uptime_seconds(path)

    def test_module_has_no_shell_or_network_imports(self):
        source = Path("/root/K/F/src/kk_f/tool_host_health.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & {"subprocess", "socket", "requests", "urllib", "http", "paramiko"})

    def test_module_exposes_no_caller_command_parameter(self):
        source = Path("/root/K/F/src/kk_f/tool_host_health.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        public = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "collect_host_health"]
        self.assertEqual(len(public), 1)
        self.assertEqual(len(public[0].args.args), 0)
        self.assertEqual(len(public[0].args.kwonlyargs), 0)


if __name__ == "__main__":
    unittest.main()
