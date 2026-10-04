"""Strict K-compatible tool layer over the already accepted FK action surface."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Mapping

from .action_registry import ALLOWED_ACTIONS
from .fk_client import submit as fk_submit
from .verifier import VerificationError, verify_receipt

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "TOOL_REGISTRY.json"
REGISTRY_SCHEMA = "K.TOOL.REGISTRY.1"
REQUEST_SCHEMA = "K.TOOL.REQUEST.1"
RECEIPT_SCHEMA = "K.TOOL.RECEIPT.1"
_ALLOWED_RISKS = frozenset({"L0", "L1", "L2", "L3", "L4"})


class ToolLayerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    action_id: str
    risk: str
    human_required: bool


def load_registry(path: Path = REGISTRY_PATH) -> Mapping[str, ToolSpec]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolLayerError("invalid tool registry") from exc
    if raw.get("schema") != REGISTRY_SCHEMA or set(raw) != {"schema", "tools"}:
        raise ToolLayerError("invalid tool registry envelope")
    tools = raw.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise ToolLayerError("tool registry must be non-empty object")
    out = {}
    for name, item in tools.items():
        if not isinstance(name, str) or not name or not isinstance(item, dict):
            raise ToolLayerError("invalid tool entry")
        if set(item) != {"action_id", "risk", "human_required"}:
            raise ToolLayerError("invalid tool entry keys")
        action_id = item["action_id"]
        risk = item["risk"]
        human_required = item["human_required"]
        if action_id not in ALLOWED_ACTIONS:
            raise ToolLayerError("tool maps outside accepted FK action surface")
        if risk not in _ALLOWED_RISKS or not isinstance(human_required, bool):
            raise ToolLayerError("invalid tool policy")
        out[name] = ToolSpec(name, action_id, risk, human_required)
    return out


def describe_tools(path: Path = REGISTRY_PATH) -> list[dict]:
    registry = load_registry(path)
    return [
        {
            "name": spec.name,
            "action_id": spec.action_id,
            "risk": spec.risk,
            "human_required": spec.human_required,
        }
        for spec in sorted(registry.values(), key=lambda x: x.name)
    ]


def execute_tool(
    request: object,
    *,
    transport: Callable[[str], dict] = fk_submit,
    registry_path: Path = REGISTRY_PATH,
) -> dict:
    if not isinstance(request, dict):
        raise ToolLayerError("tool request must be object")
    if set(request) != {"schema", "tool"}:
        raise ToolLayerError("tool request has unexpected fields")
    if request.get("schema") != REQUEST_SCHEMA:
        raise ToolLayerError("invalid tool request schema")
    tool_name = request.get("tool")
    registry = load_registry(registry_path)
    if not isinstance(tool_name, str) or tool_name not in registry:
        raise ToolLayerError("unknown tool")
    spec = registry[tool_name]
    receipt = transport(spec.action_id)
    if not isinstance(receipt, dict):
        raise ToolLayerError("invalid FK transport receipt")
    try:
        verification = verify_receipt(spec.action_id, receipt)
    except VerificationError as exc:
        raise ToolLayerError("FK receipt verification failed") from exc
    return {
        "schema": RECEIPT_SCHEMA,
        "tool": spec.name,
        "action_id": spec.action_id,
        "risk": spec.risk,
        "human_required": spec.human_required,
        "executed": receipt.get("outcome") == "EXECUTED",
        "verified": verification.result == "PASS",
        "verdict": verification.result,
        "fk_receipt": receipt,
    }
