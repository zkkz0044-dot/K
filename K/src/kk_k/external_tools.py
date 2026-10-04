"""Strict K external-tool catalog over the separate F-owned FK Tool Gateway."""

from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Mapping
from .external_tool_client import (
    submit_abstract_capability,
    submit_external_tool,
    submit_external_tool_with_args,
)

CATALOG_PATH = Path(__file__).resolve().parents[2] / "EXTERNAL_TOOL_CATALOG.json"
CATALOG_SCHEMA = "K.EXTERNAL.TOOL.CATALOG.2"
REQUEST_SCHEMA = "K.EXTERNAL.TOOL.REQUEST.1"
REQUEST_SCHEMA_V2 = "K.EXTERNAL.TOOL.REQUEST.2"
RECEIPT_SCHEMA = "K.EXTERNAL.TOOL.RECEIPT.1"
_ALLOWED_CLASSES = frozenset({"remote", "browser", "account", "data", "notify"})
_ALLOWED_RISKS = frozenset({"L0", "L1", "L2", "L3", "L4"})
_REQUIRED_ROUTE = "FK_TOOL_GATEWAY_V1"
_APPROVED = {
    "remote.vps.health": ("HOST_HEALTH_V1", None),
    "files.read": ("FILE_READ_V1", "FILES_READ_1"),
    "browser.search": ("WEB_SEARCH_V1", "WEB_SEARCH_1"),
}


class ExternalToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExternalToolSpec:
    name: str
    tool_class: str
    risk: str
    enabled: bool
    human_required: bool
    authority_route: str
    verifier: str | None
    args_schema: str | None


def load_external_catalog(path: Path = CATALOG_PATH) -> Mapping[str, ExternalToolSpec]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalToolError("invalid external tool catalog") from exc
    if raw.get("schema") != CATALOG_SCHEMA or set(raw) != {"schema", "tools"}:
        raise ExternalToolError("invalid external catalog envelope")
    tools = raw.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise ExternalToolError("external catalog must be non-empty")
    out = {}
    required = {
        "class",
        "risk",
        "enabled",
        "human_required",
        "authority_route",
        "verifier",
        "args_schema",
    }
    for name, item in tools.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(item, dict)
            or set(item) != required
        ):
            raise ExternalToolError("invalid external tool entry")
        cls = item["class"]
        risk = item["risk"]
        enabled = item["enabled"]
        hr = item["human_required"]
        route = item["authority_route"]
        verifier = item["verifier"]
        args_schema = item["args_schema"]
        if (
            cls not in _ALLOWED_CLASSES
            or risk not in _ALLOWED_RISKS
            or not isinstance(enabled, bool)
            or not isinstance(hr, bool)
            or route != _REQUIRED_ROUTE
        ):
            raise ExternalToolError("invalid external tool policy")
        if verifier is not None and not isinstance(verifier, str):
            raise ExternalToolError("invalid verifier")
        if args_schema is not None and not isinstance(args_schema, str):
            raise ExternalToolError("invalid args schema")
        approved = _APPROVED.get(name)
        if enabled and (approved is None or approved != (verifier, args_schema)):
            raise ExternalToolError("enabled external tool lacks approved contract")
        if not enabled and (verifier is not None or args_schema is not None):
            raise ExternalToolError("disabled tool must have no active contract")
        out[name] = ExternalToolSpec(name, cls, risk, enabled, hr, route, verifier, args_schema)
    return out


def external_catalog_status(path: Path = CATALOG_PATH) -> list[dict]:
    return [
        {
            "name": s.name,
            "class": s.tool_class,
            "risk": s.risk,
            "enabled": s.enabled,
            "human_required": s.human_required,
            "authority_route": s.authority_route,
            "verifier": s.verifier,
            "args_schema": s.args_schema,
            "state": "ENABLED" if s.enabled else "DISABLED_PENDING_REVIEW",
        }
        for s in sorted(load_external_catalog(path).values(), key=lambda x: x.name)
    ]


def _verify_veto(receipt: dict) -> bool:
    ev = receipt.get("evidence")
    if (
        not isinstance(ev, dict)
        or set(ev) != {"kind", "reason_code", "validation_stage"}
        or ev.get("kind") != "VETO"
    ):
        raise ExternalToolError("invalid external veto evidence")
    return False


def _verify_host_health(r: dict) -> bool:
    if r.get("outcome") == "VETO":
        return _verify_veto(r)
    ev = r.get("evidence")
    if (
        r.get("outcome") != "EXECUTED"
        or not isinstance(ev, dict)
        or set(ev) != {"kind", "health"}
        or ev.get("kind") != "HOST_HEALTH"
    ):
        raise ExternalToolError("invalid host health evidence")
    h = ev["health"]
    req = {"schema", "uptime_seconds", "cpu_count", "load", "memory", "disk_root"}
    if (
        not isinstance(h, dict)
        or set(h) != req
        or h.get("schema") != "F.TOOL.HOST_HEALTH.1"
        or type(h.get("uptime_seconds")) is not int
        or h["uptime_seconds"] < 0
        or type(h.get("cpu_count")) is not int
        or h["cpu_count"] < 1
    ):
        raise ExternalToolError("invalid host health payload")
    return True


def _verify_file_read(r: dict) -> bool:
    if r.get("outcome") == "VETO":
        return _verify_veto(r)
    ev = r.get("evidence")
    if (
        r.get("outcome") != "EXECUTED"
        or not isinstance(ev, dict)
        or set(ev) != {"kind", "file"}
        or ev.get("kind") != "FILE_READ"
    ):
        raise ExternalToolError("invalid file evidence")
    f = ev["file"]
    req = {"schema", "path", "content", "truncated"}
    if (
        not isinstance(f, dict)
        or set(f) != req
        or f.get("schema") != "F.TOOL.FILE_READ.1"
        or not isinstance(f.get("path"), str)
        or not f["path"].startswith("/root/K/")
        or not isinstance(f.get("content"), str)
        or len(f["content"]) > 2048
        or not isinstance(f.get("truncated"), bool)
    ):
        raise ExternalToolError("invalid file payload")
    return True


def _verify_web_search(r: dict) -> bool:
    if r.get("outcome") == "VETO":
        return _verify_veto(r)
    ev = r.get("evidence")
    if (
        r.get("outcome") != "EXECUTED"
        or not isinstance(ev, dict)
        or set(ev) != {"kind", "search"}
        or ev.get("kind") != "WEB_SEARCH"
    ):
        raise ExternalToolError("invalid search evidence")
    s = ev["search"]
    if (
        not isinstance(s, dict)
        or set(s) != {"schema", "query", "results"}
        or s.get("schema") != "F.TOOL.WEB_SEARCH.1"
        or not isinstance(s.get("query"), str)
        or not isinstance(s.get("results"), list)
        or len(s["results"]) > 3
    ):
        raise ExternalToolError("invalid search payload")
    for x in s["results"]:
        if (
            not isinstance(x, dict)
            or set(x) != {"title", "url", "snippet"}
            or not all(isinstance(x[k], str) for k in x)
            or not x["url"].startswith(("http://", "https://"))
        ):
            raise ExternalToolError("invalid search item")
    return True


def _validate_args(schema: str, args: object) -> dict:
    if not isinstance(args, dict):
        raise ExternalToolError("tool args must be object")
    if schema == "FILES_READ_1":
        if (
            set(args) != {"path"}
            or not isinstance(args["path"], str)
            or not (1 <= len(args["path"]) <= 512)
        ):
            raise ExternalToolError("invalid files args")
    elif schema == "WEB_SEARCH_1":
        if (
            set(args) != {"query"}
            or not isinstance(args["query"], str)
            or not (1 <= len(args["query"]) <= 200)
            or any(ord(c) < 32 for c in args["query"])
        ):
            raise ExternalToolError("invalid search args")
    else:
        raise ExternalToolError("unknown args schema")
    return dict(args)



def verify_external_receipt(
    receipt: object,
    *,
    catalog_path: Path = CATALOG_PATH,
) -> dict:
    if (
        not isinstance(receipt, dict)
        or set(receipt) != {"schema", "tool", "outcome", "evidence"}
        or receipt.get("schema") != "FK_TOOL.F_RECEIPT.1"
        or not isinstance(receipt.get("tool"), str)
    ):
        raise ExternalToolError("external transport receipt mismatch")
    name = receipt["tool"]
    catalog = load_external_catalog(catalog_path)
    if name not in catalog:
        raise ExternalToolError("receipt tool is not catalogued")
    spec = catalog[name]
    if not spec.enabled:
        raise ExternalToolError("receipt tool is disabled")
    if spec.verifier == "HOST_HEALTH_V1":
        verified = _verify_host_health(receipt)
    elif spec.verifier == "FILE_READ_V1":
        verified = _verify_file_read(receipt)
    elif spec.verifier == "WEB_SEARCH_V1":
        verified = _verify_web_search(receipt)
    else:
        raise ExternalToolError("external verifier unavailable")
    return {
        "schema": RECEIPT_SCHEMA,
        "tool": name,
        "risk": spec.risk,
        "human_required": spec.human_required,
        "executed": receipt.get("outcome") == "EXECUTED",
        "verified": verified,
        "verdict": "PASS" if verified else "VETO",
        "fk_tool_receipt": receipt,
    }


def execute_abstract_read(
    kind: str,
    *,
    query: str | None = None,
    path: str | None = None,
    transport=submit_abstract_capability,
    catalog_path: Path = CATALOG_PATH,
) -> dict:
    if kind not in {"CURRENT_EXTERNAL", "PROJECT_FILE", "VPS_HEALTH"}:
        raise ExternalToolError("invalid abstract read kind")
    try:
        receipt = transport(kind, query=query, path=path)
    except Exception as exc:
        raise ExternalToolError("abstract capability transport failed") from exc
    return verify_external_receipt(receipt, catalog_path=catalog_path)

def execute_external_tool(
    request: object,
    *,
    transport: Callable[[str], dict] = submit_external_tool,
    transport_args: Callable[[str, dict], dict] = submit_external_tool_with_args,
    catalog_path: Path = CATALOG_PATH,
) -> dict:
    if not isinstance(request, dict):
        raise ExternalToolError("external tool request must be object")
    schema = request.get("schema")
    if schema == REQUEST_SCHEMA:
        if set(request) != {"schema", "tool"}:
            raise ExternalToolError("external tool request has unexpected fields")
    elif schema == REQUEST_SCHEMA_V2:
        if set(request) != {"schema", "tool", "args"}:
            raise ExternalToolError("parameterized external request has unexpected fields")
    else:
        raise ExternalToolError("invalid external tool request schema")
    name = request.get("tool")
    catalog = load_external_catalog(catalog_path)
    if not isinstance(name, str) or name not in catalog:
        raise ExternalToolError("unknown external tool")
    spec = catalog[name]
    if not spec.enabled:
        raise ExternalToolError("external tool disabled")
    if spec.args_schema is None:
        if schema != REQUEST_SCHEMA:
            raise ExternalToolError("tool does not accept args")
        receipt = transport(name)
    else:
        if schema != REQUEST_SCHEMA_V2:
            raise ExternalToolError("tool requires args")
        receipt = transport_args(name, _validate_args(spec.args_schema, request["args"]))
    if not isinstance(receipt, dict) or receipt.get("tool") != name:
        raise ExternalToolError("external transport receipt mismatch")
    return verify_external_receipt(receipt, catalog_path=catalog_path)
