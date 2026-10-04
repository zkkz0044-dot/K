"""F-owned gateway for the deliberately small external capability surface."""

from __future__ import annotations
import json, os, socket
from pathlib import Path, PurePosixPath
from typing import Callable
from .fk_peer_identity import (
    FKPeerIdentityError,
    authorize_peer,
    cgroup_contains_unit,
    peer_credentials,
)
from .tool_host_health import HostHealthError, collect_host_health
from .tool_file_read import FileReadError, read_project_file
from .tool_web_search import WebSearchError, search_web

REQUEST_SCHEMA = "FK_TOOL.REQUEST.1"
REQUEST_SCHEMA_V2 = "FK_TOOL.REQUEST.2"
ABSTRACT_REQUEST_SCHEMA = "FK_CAPABILITY.REQUEST.1"
RECEIPT_SCHEMA = "FK_TOOL.F_RECEIPT.1"
ERROR_SCHEMA = "FK_TOOL.ERROR.1"
DEFAULT_ADDRESS = "\0kk-fk-tool-v1"
MAX_REQUEST_BYTES = 24576
MAX_RESPONSE_BYTES = 16384
ENABLED_TOOLS = frozenset({"remote.vps.health", "files.read", "browser.search"})
PARAM_TOOLS = frozenset({"files.read", "browser.search"})
ABSTRACT_KINDS = frozenset({"CURRENT_EXTERNAL", "PROJECT_FILE", "VPS_HEALTH"})
CAPABILITY_REGISTRY_PATH = Path("/root/K/F/capabilities/capability-registry.json")


class FKToolGatewayError(ValueError):
    pass


def _strict_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise FKToolGatewayError("duplicate JSON key")
        out[k] = v
    return out


def parse_request(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REQUEST_BYTES:
        raise FKToolGatewayError("invalid request size")
    try:
        v = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs)
    except Exception as exc:
        raise FKToolGatewayError("invalid request") from exc
    if not isinstance(v, dict):
        raise FKToolGatewayError("request must be object")
    schema = v.get("schema")

    if schema == ABSTRACT_REQUEST_SCHEMA:
        if set(v) != {"schema", "kind", "query", "path"}:
            raise FKToolGatewayError("invalid abstract request")
        kind, query, path = v.get("kind"), v.get("query"), v.get("path")
        if kind not in ABSTRACT_KINDS:
            raise FKToolGatewayError("invalid abstract kind")
        if kind == "CURRENT_EXTERNAL":
            if (
                not isinstance(query, str)
                or not (1 <= len(query) <= 200)
                or any(ord(c) < 32 for c in query)
                or path is not None
            ):
                raise FKToolGatewayError("invalid abstract external request")
        elif kind == "PROJECT_FILE":
            if (
                query is not None
                or not isinstance(path, str)
                or not (1 <= len(path) <= 512)
                or not path.startswith("/root/K/K/")
                or path.endswith("/")
                or "\\" in path
                or str(PurePosixPath(path)) != path
                or any(part in {".", ".."} for part in path.split("/")[1:])
            ):
                raise FKToolGatewayError("invalid abstract file request")
        elif kind == "VPS_HEALTH":
            if query is not None or path is not None:
                raise FKToolGatewayError("invalid abstract health request")
        return v

    tool = v.get("tool")
    if not isinstance(tool, str) or tool not in ENABLED_TOOLS:
        raise FKToolGatewayError("unknown tool")
    if schema == REQUEST_SCHEMA:
        if set(v) != {"schema", "tool"} or tool in PARAM_TOOLS:
            raise FKToolGatewayError("invalid v1 request")
    elif schema == REQUEST_SCHEMA_V2:
        if (
            set(v) != {"schema", "tool", "args"}
            or tool not in PARAM_TOOLS
            or not isinstance(v.get("args"), dict)
        ):
            raise FKToolGatewayError("invalid v2 request")
    else:
        raise FKToolGatewayError("unsupported request schema")
    return v


def load_capability_registry(path: Path = CAPABILITY_REGISTRY_PATH) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FKToolGatewayError("capability registry unavailable") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "bindings"}
        or value.get("schema") != "F.CAPABILITY.REGISTRY.1"
        or not isinstance(value.get("bindings"), dict)
    ):
        raise FKToolGatewayError("invalid capability registry")
    bindings = value["bindings"]
    if set(bindings) != ABSTRACT_KINDS:
        raise FKToolGatewayError("capability registry mismatch")
    out = {}
    for kind, item in bindings.items():
        if (
            not isinstance(item, dict)
            or set(item) != {"tool", "args_from"}
            or item.get("tool") not in ENABLED_TOOLS
            or not isinstance(item.get("args_from"), list)
            or len(item["args_from"]) > 2
            or any(x not in {"query", "path"} for x in item["args_from"])
            or len(item["args_from"]) != len(set(item["args_from"]))
        ):
            raise FKToolGatewayError("invalid capability binding")
        if kind == "CURRENT_EXTERNAL" and item["args_from"] != ["query"]:
            raise FKToolGatewayError("CURRENT_EXTERNAL registry mismatch")
        if kind == "PROJECT_FILE" and item["args_from"] != ["path"]:
            raise FKToolGatewayError("PROJECT_FILE registry mismatch")
        if kind == "VPS_HEALTH" and item["args_from"] != []:
            raise FKToolGatewayError("VPS_HEALTH registry mismatch")
        out[kind] = {"tool": item["tool"], "args_from": list(item["args_from"])}
    return out


def resolve_abstract_request(
    req: dict,
    *,
    registry_path: Path = CAPABILITY_REGISTRY_PATH,
) -> tuple[str, dict | None]:
    if not isinstance(req, dict) or req.get("schema") != ABSTRACT_REQUEST_SCHEMA:
        raise FKToolGatewayError("validated abstract request required")
    bindings = load_capability_registry(registry_path)
    item = bindings.get(req["kind"])
    if item is None:
        raise FKToolGatewayError("unresolved abstract capability")
    args = {name: req[name] for name in item["args_from"]}
    return item["tool"], (args or None)


def _request_tool_args(req: dict) -> tuple[str, dict | None]:
    if req.get("schema") == ABSTRACT_REQUEST_SCHEMA:
        return resolve_abstract_request(req)
    return req["tool"], req.get("args")


def _veto(tool: str, reason_code: str, stage: str) -> dict:
    return {
        "schema": RECEIPT_SCHEMA,
        "tool": tool,
        "outcome": "VETO",
        "evidence": {"kind": "VETO", "reason_code": reason_code, "validation_stage": stage},
    }


def dispatch(tool: str, *, peer_uid: int, allowed_uid: int, args: dict | None = None) -> dict:
    if peer_uid != allowed_uid:
        return _veto(tool, "PEER_AUTH_DENY", "PEER_AUTH")
    if tool == "remote.vps.health":
        if args is not None:
            return _veto(tool, "PARAMS_DENIED", "TOOL_POLICY")
        try:
            health = collect_host_health()
        except HostHealthError:
            return _veto(tool, "TOOL_READ_FAILED", "TOOL_EXECUTION")
        return {
            "schema": RECEIPT_SCHEMA,
            "tool": tool,
            "outcome": "EXECUTED",
            "evidence": {"kind": "HOST_HEALTH", "health": health},
        }
    if tool == "files.read":
        if not isinstance(args, dict) or set(args) != {"path"}:
            return _veto(tool, "PARAMS_INVALID", "TOOL_POLICY")
        try:
            data = read_project_file(args["path"])
        except FileReadError:
            return _veto(tool, "FILE_POLICY_DENY", "TOOL_EXECUTION")
        return {
            "schema": RECEIPT_SCHEMA,
            "tool": tool,
            "outcome": "EXECUTED",
            "evidence": {"kind": "FILE_READ", "file": data},
        }
    if tool == "browser.search":
        if not isinstance(args, dict) or set(args) != {"query"}:
            return _veto(tool, "PARAMS_INVALID", "TOOL_POLICY")
        try:
            data = search_web(args["query"])
        except WebSearchError:
            return _veto(tool, "SEARCH_UNAVAILABLE", "TOOL_EXECUTION")
        return {
            "schema": RECEIPT_SCHEMA,
            "tool": tool,
            "outcome": "EXECUTED",
            "evidence": {"kind": "WEB_SEARCH", "search": data},
        }
    return _veto(tool, "TOOL_DISABLED", "TOOL_POLICY")


def _recv_line(conn):
    buf = bytearray()
    while True:
        x = conn.recv(min(512, MAX_REQUEST_BYTES + 1 - len(buf)))
        if not x:
            break
        buf.extend(x)
        if len(buf) > MAX_REQUEST_BYTES:
            raise FKToolGatewayError("request too large")
        if b"\n" in x:
            break
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise FKToolGatewayError("invalid frame")
    return bytes(buf[:-1])


def _send(conn, value):
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FKToolGatewayError("response too large")
    try:
        conn.sendall(raw)
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def handle_connection(
    conn, *, allowed_uid: int | None = None, allowed_cgroup_unit: str | None = None
) -> None:
    try:
        pid, uid, _gid = peer_credentials(conn)
        req = parse_request(_recv_line(conn))
        try:
            ok = authorize_peer(
                pid=pid, uid=uid, allowed_uid=allowed_uid, allowed_cgroup_unit=allowed_cgroup_unit
            )
        except FKPeerIdentityError:
            ok = False
        if not ok:
            if req.get("schema") == ABSTRACT_REQUEST_SCHEMA:
                _send(conn, {"schema": ERROR_SCHEMA, "reason_code": "PEER_AUTH_DENY", "stage": "PEER_AUTH"})
            else:
                _send(conn, _veto(req["tool"], "PEER_AUTH_DENY", "PEER_AUTH"))
            return
        tool, args = _request_tool_args(req)
        _send(conn, dispatch(tool, peer_uid=uid, allowed_uid=uid, args=args))
    except (FKToolGatewayError, FKPeerIdentityError):
        _send(
            conn,
            {"schema": ERROR_SCHEMA, "reason_code": "INVALID_REQUEST", "stage": "REQUEST_PARSE"},
        )


def _validate_peer_policy(allowed_uid, allowed_cgroup_unit):
    if allowed_uid is None and allowed_cgroup_unit is None:
        allowed_uid = os.getuid()
    if allowed_uid is not None and allowed_cgroup_unit is not None:
        raise FKToolGatewayError("ambiguous peer policy")
    if allowed_uid is not None and (type(allowed_uid) is not int or allowed_uid < 0):
        raise FKToolGatewayError("invalid allowed_uid")
    if allowed_cgroup_unit is not None:
        try:
            cgroup_contains_unit("", allowed_cgroup_unit)
        except FKPeerIdentityError as exc:
            raise FKToolGatewayError("invalid cgroup") from exc
    return allowed_uid, allowed_cgroup_unit


def serve_once(
    *,
    address=DEFAULT_ADDRESS,
    allowed_uid=None,
    allowed_cgroup_unit=None,
    ready: Callable[[], None] | None = None,
):
    allowed_uid, allowed_cgroup_unit = _validate_peer_policy(allowed_uid, allowed_cgroup_unit)
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKToolGatewayError("abstract AF_UNIX required")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(address)
        s.listen(4)
        if ready:
            ready()
        c, _ = s.accept()
        with c:
            handle_connection(c, allowed_uid=allowed_uid, allowed_cgroup_unit=allowed_cgroup_unit)
    finally:
        s.close()


def serve_forever(*, address=DEFAULT_ADDRESS, allowed_uid=None, allowed_cgroup_unit=None):
    allowed_uid, allowed_cgroup_unit = _validate_peer_policy(allowed_uid, allowed_cgroup_unit)
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKToolGatewayError("abstract AF_UNIX required")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(address)
        s.listen(16)
        while True:
            c, _ = s.accept()
            with c:
                handle_connection(
                    c, allowed_uid=allowed_uid, allowed_cgroup_unit=allowed_cgroup_unit
                )
    finally:
        s.close()


# FKP06 client identities for the external-tool gateway only.
ALLOWED_TOOL_CLIENT_UNITS = frozenset(
    {
        "kk-k-runtime.service",
        "kk-gpt-tool-runtime.service",
    }
)


def _authorize_tool_client_units(pid: int, uid: int, units: frozenset[str]) -> bool:
    if uid == 0 or not isinstance(units, frozenset) or not units:
        return False
    for unit in units:
        try:
            if authorize_peer(pid=pid, uid=uid, allowed_cgroup_unit=unit):
                return True
        except FKPeerIdentityError:
            continue
    return False


def handle_connection_multi(conn, *, allowed_cgroup_units: frozenset[str]) -> None:
    try:
        pid, uid, _gid = peer_credentials(conn)
        req = parse_request(_recv_line(conn))
        if not _authorize_tool_client_units(pid, uid, allowed_cgroup_units):
            if req.get("schema") == ABSTRACT_REQUEST_SCHEMA:
                _send(conn, {"schema": ERROR_SCHEMA, "reason_code": "PEER_AUTH_DENY", "stage": "PEER_AUTH"})
            else:
                _send(conn, _veto(req["tool"], "PEER_AUTH_DENY", "PEER_AUTH"))
            return
        tool, args = _request_tool_args(req)
        _send(conn, dispatch(tool, peer_uid=uid, allowed_uid=uid, args=args))
    except (FKToolGatewayError, FKPeerIdentityError):
        _send(
            conn,
            {"schema": ERROR_SCHEMA, "reason_code": "INVALID_REQUEST", "stage": "REQUEST_PARSE"},
        )


def serve_forever_multi(
    *,
    address: str = DEFAULT_ADDRESS,
    allowed_cgroup_units: frozenset[str] = ALLOWED_TOOL_CLIENT_UNITS,
) -> None:
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKToolGatewayError("abstract AF_UNIX required")
    if not isinstance(allowed_cgroup_units, frozenset) or not allowed_cgroup_units:
        raise FKToolGatewayError("tool client units required")
    for unit in allowed_cgroup_units:
        try:
            cgroup_contains_unit("", unit)
        except FKPeerIdentityError as exc:
            raise FKToolGatewayError("invalid tool client unit") from exc
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(address)
        server.listen(16)
        while True:
            conn, _ = server.accept()
            with conn:
                handle_connection_multi(conn, allowed_cgroup_units=allowed_cgroup_units)
    finally:
        server.close()
