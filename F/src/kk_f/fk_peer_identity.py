from __future__ import annotations

import re
import socket
import struct

UNIT_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,96}\.service$")
MAX_CGROUP_BYTES = 16384


class FKPeerIdentityError(ValueError):
    pass


def peer_credentials(conn: socket.socket) -> tuple[int, int, int]:
    if not hasattr(socket, "SO_PEERCRED"):
        raise FKPeerIdentityError("SO_PEERCRED unavailable")
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", raw)
    if pid <= 0 or uid < 0 or gid < 0:
        raise FKPeerIdentityError("invalid peer credentials")
    return int(pid), int(uid), int(gid)


def _read_cgroup(pid: int) -> str:
    if type(pid) is not int or pid <= 0:
        raise FKPeerIdentityError("invalid peer pid")
    path = f"/proc/{pid}/cgroup"
    try:
        with open(path, "rb", buffering=0) as handle:
            raw = handle.read(MAX_CGROUP_BYTES + 1)
    except OSError as exc:
        raise FKPeerIdentityError("peer cgroup unavailable") from exc
    if len(raw) > MAX_CGROUP_BYTES:
        raise FKPeerIdentityError("peer cgroup too large")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FKPeerIdentityError("peer cgroup unreadable") from exc


def cgroup_contains_unit(cgroup_text: str, unit: str) -> bool:
    if not isinstance(cgroup_text, str):
        raise FKPeerIdentityError("invalid cgroup text")
    if not isinstance(unit, str) or UNIT_RE.fullmatch(unit) is None:
        raise FKPeerIdentityError("invalid cgroup unit")
    for line in cgroup_text.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        path = parts[2]
        components = [item for item in path.split("/") if item]
        if unit in components:
            return True
    return False


def authorize_peer(
    *, pid: int, uid: int, allowed_uid: int | None = None, allowed_cgroup_unit: str | None = None
) -> bool:
    if allowed_uid is not None and allowed_cgroup_unit is not None:
        raise FKPeerIdentityError("ambiguous peer policy")
    if allowed_uid is None and allowed_cgroup_unit is None:
        raise FKPeerIdentityError("peer policy required")
    if allowed_uid is not None:
        if type(allowed_uid) is not int or allowed_uid < 0:
            raise FKPeerIdentityError("invalid allowed uid")
        return uid == allowed_uid
    if uid == 0:
        return False
    text = _read_cgroup(pid)
    return cgroup_contains_unit(text, allowed_cgroup_unit)
