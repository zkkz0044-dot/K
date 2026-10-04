from __future__ import annotations

import json
import os
import socket
import struct
from pathlib import Path

ADDRESS = "/run/kk-model-ipc/model.sock"
PROVIDER_CONFIG = "/run/kk-model-gateway-ro/cognition-providers.json"
DIALOGUE_CGROUP = "/system.slice/kk-k-runtime.service"
WORLD_CGROUP = "/system.slice/kk-world-cognition-runtime.service"


from .role_policy import instructions_for_role, max_output_tokens

from .gateway_protocol import (
    MAX_RESPONSE,
    DIALOGUE_ROLES,
    GatewayError,
    recv_line,
    strict_json,
)

def peer_credentials(conn: socket.socket):
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", raw)


def peer_cgroup(pid: int) -> str:
    if not isinstance(pid, int) or pid <= 0:
        raise GatewayError("PEER_CGROUP_INVALID")
    # ProtectProc=invisible intentionally hides /proc/<peer>/cgroup from this
    # unprivileged gateway. Authenticate the live SO_PEERCRED PID against the
    # two exact service cgroups through cgroup v2's read-only cgroup.procs.
    for expected in (DIALOGUE_CGROUP, WORLD_CGROUP):
        path = Path("/sys/fs/cgroup") / expected.lstrip("/") / "cgroup.procs"
        try:
            members = {int(x) for x in path.read_text().splitlines() if x.isdigit()}
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise GatewayError("PEER_CGROUP_UNAVAILABLE") from exc
        if pid in members:
            return expected
    return ""






def _relay_call(path: str, req: dict, *, timeout: int, default_provider: str) -> tuple[str, str]:
    raw = (json.dumps(req, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    c.settimeout(timeout)
    try:
        c.connect(path)
        c.sendall(raw)
        buf = bytearray()
        while b"\n" not in buf:
            chunk = c.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > MAX_RESPONSE:
                raise GatewayError("MODEL_RELAY_RESPONSE_TOO_LARGE")
    except OSError as exc:
        raise GatewayError("MODEL_RELAY_UNAVAILABLE") from exc
    finally:
        c.close()
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise GatewayError("MODEL_RELAY_INVALID_FRAME")
    try:
        v = json.loads(bytes(buf[:-1]).decode("utf-8"))
    except Exception as exc:
        raise GatewayError("MODEL_RELAY_INVALID_JSON") from exc
    if not isinstance(v, dict) or v.get("schema") != "K.MODEL.RELAY.RESPONSE.2":
        raise GatewayError("MODEL_RELAY_INVALID_RESPONSE")
    if v.get("status") != "PASS":
        raise GatewayError(str(v.get("reason_code", "MODEL_RELAY_FAILED")))
    text = v.get("text")
    provider = v.get("provider_id", default_provider)
    if not isinstance(provider, str) or not provider or len(provider) > 96:
        raise GatewayError("MODEL_PROVIDER_INVALID")
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text.encode("utf-8")) > 4096
        or "\x00" in text
    ):
        raise GatewayError("MODEL_OUTPUT_INVALID")
    return text.strip(), provider


def _validated_provider(name: str, item: object) -> dict:
    if not isinstance(name, str) or not name or len(name) > 64 or not isinstance(item, dict):
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    enabled = item.get("enabled")
    if not isinstance(enabled, bool):
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    sock, provider_id = item.get("socket"), item.get("provider_id")
    if not isinstance(sock, str) or not sock.startswith("/run/kk-model-ipc/"):
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 96:
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    timeout = item.get("timeout_seconds", 125)
    if not isinstance(timeout, int) or not (1 <= timeout <= 125):
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    return {
        "name": name,
        "socket": sock,
        "provider_id": provider_id,
        "enabled": enabled,
        "timeout_seconds": timeout,
    }


def _provider_chain(role: str) -> list[dict]:
    try:
        v = json.loads(Path(PROVIDER_CONFIG).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID") from exc
    if not isinstance(v, dict):
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    providers = v.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")

    # Backward-compatible v1: exactly one active provider.
    if v.get("schema") == "K.COGNITION.PROVIDERS.1":
        active = v.get("active_provider")
        if not isinstance(active, str) or active not in providers:
            raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
        item = _validated_provider(active, providers[active])
        if not item["enabled"]:
            raise GatewayError("MODEL_PROVIDER_DISABLED")
        return [item]

    if v.get("schema") != "K.COGNITION.PROVIDERS.2":
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    routes = v.get("routes")
    if not isinstance(routes, dict):
        raise GatewayError("MODEL_PROVIDER_CONFIG_INVALID")
    names = routes.get(role, routes.get("default"))
    if not isinstance(names, list) or not names or len(names) > 8:
        raise GatewayError("MODEL_PROVIDER_ROUTE_INVALID")
    if len(names) != len(set(names)):
        raise GatewayError("MODEL_PROVIDER_ROUTE_INVALID")

    chain = []
    for name in names:
        if not isinstance(name, str) or name not in providers:
            raise GatewayError("MODEL_PROVIDER_ROUTE_INVALID")
        item = _validated_provider(name, providers[name])
        if item["enabled"]:
            chain.append(item)
    if not chain:
        raise GatewayError("MODEL_PROVIDER_DISABLED")
    return chain


def run_model(role: str, prompt: str, media: list[dict] | None = None) -> tuple[str, str]:
    media = list(media or [])
    req = (
        {"schema":"K.MODEL.RELAY.REQUEST.3","instructions":instructions_for_role(role),"input":prompt,"media":media,"max_output_tokens":max_output_tokens(role)}
        if media else
        {"schema":"K.MODEL.RELAY.REQUEST.2","instructions":instructions_for_role(role),"input":prompt,"max_output_tokens":max_output_tokens(role)}
    )
    for provider in _provider_chain(role):
        try:
            return _relay_call(
                provider["socket"],
                req,
                timeout=provider["timeout_seconds"],
                default_provider=provider["provider_id"],
            )
        except GatewayError:
            continue
    raise GatewayError("MODEL_PROVIDER_CHAIN_EXHAUSTED")


def send(conn: socket.socket, value: dict) -> None:
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    if len(raw) > MAX_RESPONSE:
        raise GatewayError("RESPONSE_TOO_LARGE")
    conn.sendall(raw)


def handle(conn: socket.socket) -> None:
    try:
        raw = recv_line(conn)
        pid, uid, _gid = peer_credentials(conn)
        req = strict_json(raw)
        cgroup = peer_cgroup(pid)
        allowed = DIALOGUE_CGROUP if req["role"] in DIALOGUE_ROLES else WORLD_CGROUP
        if uid == 0 or cgroup != allowed:
            send(conn, {"schema": "K.MODEL.ERROR.1", "reason_code": "PEER_AUTH_DENY"})
            return
        text, provider = run_model(req["role"], req["prompt"], req.get("media"))
        send(
            conn,
            {
                "schema": "K.MODEL.RESPONSE.1",
                "provider_id": provider,
                "trust": "UNTRUSTED",
                "text": text,
            },
        )
    except GatewayError as exc:
        try:
            send(conn, {"schema": "K.MODEL.ERROR.1", "reason_code": str(exc)})
        except (GatewayError, OSError):
            pass
    except OSError:
        return


def main() -> int:
    if os.geteuid() == 0:
        raise GatewayError("MODEL_GATEWAY_MUST_BE_NONROOT")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        os.unlink(ADDRESS)
    except FileNotFoundError:
        pass
    server.bind(ADDRESS)
    os.chmod(ADDRESS, 0o666)
    server.listen(8)
    while True:
        conn, _ = server.accept()
        with conn:
            handle(conn)


if __name__ == "__main__":
    raise SystemExit(main())
