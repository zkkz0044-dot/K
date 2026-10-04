"""Strict verifier/contracts for external read-only connectors."""

from __future__ import annotations
from dataclasses import dataclass
import re

REQ_SCHEMA = "K.CONNECTOR.REQUEST.1"
RECEIPT_SCHEMA = "K.CONNECTOR.RECEIPT.1"
_ALLOWED = frozenset({"github.read", "gmail.search"})
_OWNER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class ConnectorBrokerError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectorRequest:
    tool: str
    args: dict


def parse_request(value: object) -> ConnectorRequest:
    if not isinstance(value, dict) or set(value) != {"schema", "tool", "args"}:
        raise ConnectorBrokerError("exact connector request fields required")
    if (
        value.get("schema") != REQ_SCHEMA
        or value.get("tool") not in _ALLOWED
        or not isinstance(value.get("args"), dict)
    ):
        raise ConnectorBrokerError("invalid connector request")
    tool = value["tool"]
    args = value["args"]
    if tool == "github.read":
        if (
            set(args) != {"repository"}
            or not isinstance(args["repository"], str)
            or _REPO_RE.fullmatch(args["repository"]) is None
        ):
            raise ConnectorBrokerError("invalid github args")
    elif tool == "gmail.search":
        if (
            set(args) != {"query", "limit"}
            or not isinstance(args["query"], str)
            or not (1 <= len(args["query"]) <= 200)
        ):
            raise ConnectorBrokerError("invalid gmail args")
        if type(args["limit"]) is not int or not (1 <= args["limit"] <= 5):
            raise ConnectorBrokerError("invalid gmail limit")
        if any(ord(c) < 32 for c in args["query"]):
            raise ConnectorBrokerError("invalid gmail query")
    return ConnectorRequest(tool, dict(args))


def _exact(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ConnectorBrokerError(f"{label} exact fields required")
    return value


def verify_github_receipt(receipt: object) -> dict:
    r = _exact(receipt, {"schema", "tool", "status", "data"}, "github receipt")
    if r["schema"] != RECEIPT_SCHEMA or r["tool"] != "github.read" or r["status"] != "PASS":
        raise ConnectorBrokerError("invalid github receipt envelope")
    d = _exact(
        r["data"], {"repository", "visibility", "default_branch", "archived", "size"}, "github data"
    )
    if not isinstance(d["repository"], str) or _REPO_RE.fullmatch(d["repository"]) is None:
        raise ConnectorBrokerError("invalid github repository")
    if d["visibility"] not in {"public", "private", "internal"} or not isinstance(
        d["default_branch"], str
    ):
        raise ConnectorBrokerError("invalid github metadata")
    if not isinstance(d["archived"], bool) or type(d["size"]) is not int or d["size"] < 0:
        raise ConnectorBrokerError("invalid github metadata")
    return d


def verify_gmail_receipt(receipt: object) -> list[dict]:
    r = _exact(receipt, {"schema", "tool", "status", "data"}, "gmail receipt")
    if r["schema"] != RECEIPT_SCHEMA or r["tool"] != "gmail.search" or r["status"] != "PASS":
        raise ConnectorBrokerError("invalid gmail receipt envelope")
    if not isinstance(r["data"], list) or len(r["data"]) > 5:
        raise ConnectorBrokerError("invalid gmail data")
    out = []
    for item in r["data"]:
        m = _exact(item, {"id", "subject", "snippet", "timestamp", "has_attachment"}, "gmail item")
        if not all(isinstance(m[k], str) for k in ("id", "subject", "snippet", "timestamp")):
            raise ConnectorBrokerError("invalid gmail text fields")
        if (
            not m["id"]
            or len(m["subject"]) > 300
            or len(m["snippet"]) > 500
            or not isinstance(m["has_attachment"], bool)
        ):
            raise ConnectorBrokerError("invalid gmail metadata")
        out.append(dict(m))
    return out


def verify_receipt(tool: str, receipt: object):
    if tool == "github.read":
        return verify_github_receipt(receipt)
    if tool == "gmail.search":
        return verify_gmail_receipt(receipt)
    raise ConnectorBrokerError("unsupported connector tool")
