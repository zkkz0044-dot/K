"""K-side FK client. External/F data remains untrusted until strict receipt verification."""

from __future__ import annotations

import json
import socket

REQUEST_SCHEMA = "FK01.REQUEST.1"
RECEIPT_SCHEMA = "FK01.F_RECEIPT.1"
ERROR_SCHEMA = "FK01.ERROR.1"
DEFAULT_ADDRESS = "\0kk-fk-v1"
MAX_RESPONSE_BYTES = 4096
RECEIPT_KEYS = frozenset({"schema", "action_id", "outcome", "evidence"})
ERROR_KEYS = frozenset({"schema", "reason_code", "stage"})


class FKClientError(RuntimeError):
    pass


def _strict_json(raw: bytes) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FKClientError("FK response must be UTF-8") from exc

    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise FKClientError("duplicate FK response key")
            out[key] = value
        return out

    try:
        value = json.loads(text, object_pairs_hook=hook)
    except FKClientError:
        raise
    except json.JSONDecodeError as exc:
        raise FKClientError("invalid FK response JSON") from exc
    if not isinstance(value, dict):
        raise FKClientError("FK response must be object")
    return value


def _recv_line(sock: socket.socket) -> bytes:
    buf = bytearray()
    while True:
        chunk = sock.recv(min(512, MAX_RESPONSE_BYTES + 1 - len(buf)))
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_RESPONSE_BYTES:
            raise FKClientError("FK response too large")
        if b"\n" in chunk:
            break
    if not buf.endswith(b"\n"):
        raise FKClientError("unterminated FK response")
    raw = bytes(buf[:-1])
    if b"\n" in raw:
        raise FKClientError("multiple FK response frames")
    return raw


def submit(action_id: str, *, address: str = DEFAULT_ADDRESS, timeout_seconds: float = 2.0) -> dict:
    if not isinstance(action_id, str):
        raise FKClientError("action_id must be string")
    if not isinstance(address, str) or not address.startswith("\0"):
        raise FKClientError("abstract AF_UNIX address required")
    request = {"schema": REQUEST_SCHEMA, "action_id": action_id}
    raw = (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_seconds)
    try:
        sock.connect(address)
        sock.sendall(raw)
        value = _strict_json(_recv_line(sock))
    except (OSError, socket.timeout) as exc:
        raise FKClientError("FK transport failed") from exc
    finally:
        sock.close()
    if value.get("schema") == ERROR_SCHEMA:
        if frozenset(value) != ERROR_KEYS:
            raise FKClientError("invalid FK error envelope")
        raise FKClientError(f"FK rejected request: {value['reason_code']}@{value['stage']}")
    if frozenset(value) != RECEIPT_KEYS or value.get("schema") != RECEIPT_SCHEMA:
        raise FKClientError("invalid FK receipt envelope")
    if value.get("action_id") != action_id:
        raise FKClientError("FK receipt action mismatch")
    return value
