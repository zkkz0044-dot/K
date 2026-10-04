"""K-side client for the separate F-owned FK tool gateway."""

from __future__ import annotations
import json, socket

REQUEST_SCHEMA = "FK_TOOL.REQUEST.1"
REQUEST_SCHEMA_V2 = "FK_TOOL.REQUEST.2"
ABSTRACT_REQUEST_SCHEMA = "FK_CAPABILITY.REQUEST.1"
RECEIPT_SCHEMA = "FK_TOOL.F_RECEIPT.1"
ERROR_SCHEMA = "FK_TOOL.ERROR.1"
DEFAULT_ADDRESS = "\0kk-fk-tool-v1"
MAX_RESPONSE_BYTES = 16384
RECEIPT_KEYS = frozenset({"schema", "tool", "outcome", "evidence"})
ERROR_KEYS = frozenset({"schema", "reason_code", "stage"})


class ExternalToolClientError(RuntimeError):
    pass


def _strict_json(raw: bytes) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExternalToolClientError("tool response must be UTF-8") from exc

    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ExternalToolClientError("duplicate tool response key")
            out[k] = v
        return out

    try:
        v = json.loads(text, object_pairs_hook=hook)
    except ExternalToolClientError:
        raise
    except json.JSONDecodeError as exc:
        raise ExternalToolClientError("invalid tool response JSON") from exc
    if not isinstance(v, dict):
        raise ExternalToolClientError("tool response must be object")
    return v


def _recv_line(sock):
    buf = bytearray()
    while True:
        x = sock.recv(min(1024, MAX_RESPONSE_BYTES + 1 - len(buf)))
        if not x:
            break
        buf.extend(x)
        if len(buf) > MAX_RESPONSE_BYTES:
            raise ExternalToolClientError("tool response too large")
        if b"\n" in x:
            break
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise ExternalToolClientError("invalid tool response frame")
    return bytes(buf[:-1])


def _submit(req: dict, tool: str | None, *, address=DEFAULT_ADDRESS, timeout_seconds=10.0) -> dict:
    raw = (
        json.dumps(req, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(raw) > 4096:
        raise ExternalToolClientError("tool request too large")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout_seconds)
    try:
        s.connect(address)
        s.sendall(raw)
        v = _strict_json(_recv_line(s))
    except (OSError, socket.timeout) as exc:
        raise ExternalToolClientError("tool transport failed") from exc
    finally:
        s.close()
    if v.get("schema") == ERROR_SCHEMA:
        if frozenset(v) != ERROR_KEYS:
            raise ExternalToolClientError("invalid tool error envelope")
        raise ExternalToolClientError(f"tool rejected request: {v['reason_code']}@{v['stage']}")
    if (
        frozenset(v) != RECEIPT_KEYS
        or v.get("schema") != RECEIPT_SCHEMA
        or not isinstance(v.get("tool"), str)
        or not v.get("tool")
        or (tool is not None and v.get("tool") != tool)
        or v.get("outcome") not in {"EXECUTED", "VETO"}
        or not isinstance(v.get("evidence"), dict)
    ):
        raise ExternalToolClientError("invalid tool receipt")
    return v


def submit_external_tool(tool: str, *, address=DEFAULT_ADDRESS, timeout_seconds=2.0) -> dict:
    if not isinstance(tool, str) or not tool:
        raise ExternalToolClientError("tool must be non-empty string")
    return _submit(
        {"schema": REQUEST_SCHEMA, "tool": tool},
        tool,
        address=address,
        timeout_seconds=timeout_seconds,
    )


def submit_external_tool_with_args(
    tool: str, args: dict, *, address=DEFAULT_ADDRESS, timeout_seconds=10.0
) -> dict:
    if not isinstance(tool, str) or not tool or not isinstance(args, dict):
        raise ExternalToolClientError("invalid parameterized tool request")
    return _submit(
        {"schema": REQUEST_SCHEMA_V2, "tool": tool, "args": args},
        tool,
        address=address,
        timeout_seconds=timeout_seconds,
    )

def submit_abstract_capability(
    kind: str,
    *,
    query: str | None = None,
    path: str | None = None,
    address=DEFAULT_ADDRESS,
    timeout_seconds=35.0,
) -> dict:
    if kind not in {"CURRENT_EXTERNAL", "PROJECT_FILE", "VPS_HEALTH"}:
        raise ExternalToolClientError("invalid abstract capability kind")
    if query is not None and not isinstance(query, str):
        raise ExternalToolClientError("invalid abstract query")
    if path is not None and not isinstance(path, str):
        raise ExternalToolClientError("invalid abstract path")
    req = {
        "schema": ABSTRACT_REQUEST_SCHEMA,
        "kind": kind,
        "query": query,
        "path": path,
    }
    return _submit(req, None, address=address, timeout_seconds=timeout_seconds)

