import json
from pathlib import Path
import tempfile
import unittest

from kk_k.tool_layer import (
    RECEIPT_SCHEMA,
    REQUEST_SCHEMA,
    ToolLayerError,
    describe_tools,
    execute_tool,
    load_registry,
)


class ToolLayerTests(unittest.TestCase):
    def test_registry_exposes_exact_accepted_surface(self):
        tools = describe_tools()
        self.assertEqual(len(tools), 5)
        self.assertEqual(
            {x["action_id"] for x in tools},
            {
                "A01_READ_PROJECT_STATE",
                "A02_READ_F_STATUS",
                "A03_RUN_F_SMOKE_TEST",
                "A04_WRITE_K_DECISION_LOG",
                "A05_NO_ACTION",
            },
        )

    def test_execute_wraps_fk_receipt(self):
        seen = []

        def fake_submit(action_id):
            seen.append(action_id)
            return {
                "schema": "FK01.F_RECEIPT.1",
                "action_id": action_id,
                "outcome": "EXECUTED",
                "evidence": {"kind": "PROJECT_STATE", "status": "ACCEPTED"},
            }

        out = execute_tool(
            {"schema": REQUEST_SCHEMA, "tool": "kk.project_state.read"},
            transport=fake_submit,
        )
        self.assertEqual(seen, ["A01_READ_PROJECT_STATE"])
        self.assertEqual(out["schema"], RECEIPT_SCHEMA)
        self.assertTrue(out["executed"])
        self.assertTrue(out["verified"])

    def test_unknown_tool_fails_closed(self):
        with self.assertRaises(ToolLayerError):
            execute_tool(
                {"schema": REQUEST_SCHEMA, "tool": "shell.exec"},
                transport=lambda _: {},
            )

    def test_request_cannot_smuggle_params_or_commands(self):
        with self.assertRaises(ToolLayerError):
            execute_tool(
                {
                    "schema": REQUEST_SCHEMA,
                    "tool": "kk.project_state.read",
                    "command": "id",
                },
                transport=lambda _: {},
            )

    def test_registry_cannot_expand_authority(self):
        bad = {
            "schema": "K.TOOL.REGISTRY.1",
            "tools": {
                "shell.exec": {
                    "action_id": "A99_SHELL_EXEC",
                    "risk": "L4",
                    "human_required": True,
                }
            },
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "registry.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ToolLayerError):
                load_registry(path)


if __name__ == "__main__":
    unittest.main()
