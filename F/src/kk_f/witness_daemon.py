"""FH03 minimal root monotonic-witness daemon; no arbitrary execution or path API."""

from __future__ import annotations

import argparse
import json
import os
import signal
import pwd
import grp
import socket
import stat
import struct
from pathlib import Path

from .monotonic_witness import (
    WitnessError,
    commit,
    load_state,
    prepare,
    recover,
    save_state,
    verify,
)

MAX_REQUEST = 4096
REQUEST_KEYS = {
    "verify": frozenset({"op", "channel", "generation", "digest"}),
    "prepare": frozenset(
        {"op", "channel", "current_generation", "current_digest", "new_generation", "new_digest"}
    ),
    "commit": frozenset({"op", "channel", "generation", "digest"}),
    "recover": frozenset({"op", "channel", "generation", "digest"}),
}


class WitnessDaemonError(RuntimeError):
    pass


def _strict_json(raw: bytes) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise WitnessDaemonError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=hook,
            parse_constant=lambda _: (_ for _ in ()).throw(WitnessDaemonError("non-finite number")),
        )
    except WitnessDaemonError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WitnessDaemonError("invalid request JSON") from exc
    if not isinstance(value, dict):
        raise WitnessDaemonError("request object required")
    op = value.get("op")
    if op not in REQUEST_KEYS or frozenset(value) != REQUEST_KEYS[op]:
        raise WitnessDaemonError("exact request schema required")
    return value


def _peer_credentials(conn: socket.socket) -> tuple[int, int, int]:
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", raw)
    return pid, uid, gid


def _peer_cgroup(pid: int) -> str:
    try:
        lines = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise WitnessDaemonError("peer cgroup unavailable") from exc
    unified = [line[3:] for line in lines if line.startswith("0::/")]
    if len(unified) != 1:
        raise WitnessDaemonError("exact unified peer cgroup required")
    return unified[0]


def _handle(state_path: str, request: dict) -> None:
    state = load_state(state_path)
    op = request["op"]
    if op == "verify":
        verify(state, request["channel"], request["generation"], request["digest"])
        return
    if op == "prepare":
        updated = prepare(
            state,
            request["channel"],
            request["current_generation"],
            request["current_digest"],
            request["new_generation"],
            request["new_digest"],
        )
    elif op == "commit":
        updated = commit(state, request["channel"], request["generation"], request["digest"])
    else:
        updated = recover(state, request["channel"], request["generation"], request["digest"])
    save_state(state_path, updated)


def run_server(
    state_path: str,
    socket_path: str,
    *,
    allowed_uid: int,
    allowed_gid: int,
    allowed_cgroup: str | None = None,
) -> int:
    if os.geteuid() != 0:
        raise WitnessDaemonError("witness daemon must run as root")
    if (
        type(allowed_uid) is not int
        or allowed_uid < 0
        or type(allowed_gid) is not int
        or allowed_gid < 0
    ):
        raise WitnessDaemonError("valid allowed uid/gid required")
    if allowed_cgroup is not None and (
        not isinstance(allowed_cgroup, str)
        or not allowed_cgroup.startswith("/")
        or "\x00" in allowed_cgroup
        or "\n" in allowed_cgroup
    ):
        raise WitnessDaemonError("valid absolute allowed cgroup required")
    state = Path(state_path)
    sock = Path(socket_path)
    info = state.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise WitnessDaemonError("witness state must be root-owned 0600-like regular file")
    load_state(state_path)
    sock.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    os.chown(sock.parent, 0, allowed_gid)
    os.chmod(sock.parent, 0o750)
    try:
        if sock.exists() or sock.is_symlink():
            sock.unlink()
    except OSError as exc:
        raise WitnessDaemonError("stale witness socket cannot be removed") from exc
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stop = False
    controller_pid: int | None = None

    def request_stop(signum, frame):
        nonlocal stop
        stop = True

    old_term = signal.signal(signal.SIGTERM, request_stop)
    old_int = signal.signal(signal.SIGINT, request_stop)
    try:
        server.bind(socket_path)
        os.chown(socket_path, 0, allowed_gid)
        os.chmod(socket_path, 0o660)
        server.listen(16)
        server.settimeout(0.2)
        while not stop:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            with conn:
                try:
                    peer_pid, peer_uid, _ = _peer_credentials(conn)
                    if peer_uid != allowed_uid:
                        raise WitnessDaemonError("unauthorized peer uid")
                    if allowed_cgroup is not None and _peer_cgroup(peer_pid) != allowed_cgroup:
                        raise WitnessDaemonError("unauthorized peer cgroup")
                    if controller_pid is None:
                        controller_pid = peer_pid
                    elif peer_pid != controller_pid:
                        if Path(f"/proc/{controller_pid}").exists():
                            raise WitnessDaemonError(
                                "unauthorized peer pid; controller already pinned"
                            )
                        controller_pid = peer_pid
                    data = bytearray()
                    while b"\n" not in data:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        data.extend(chunk)
                        if len(data) > MAX_REQUEST:
                            raise WitnessDaemonError("request too large")
                    if not data.endswith(b"\n") or data.count(b"\n") != 1:
                        raise WitnessDaemonError("single newline-terminated request required")
                    request = _strict_json(bytes(data[:-1]))
                    _handle(state_path, request)
                    response = {"ok": True}
                except (WitnessDaemonError, WitnessError, OSError) as exc:
                    response = {"ok": False, "error": str(exc)}
                conn.sendall(
                    json.dumps(response, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                )
        return 0
    finally:
        server.close()
        try:
            if sock.exists() or sock.is_symlink():
                sock.unlink()
        except OSError:
            pass
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True)
    p.add_argument("--socket", required=True)
    p.add_argument("--allowed-uid", type=int)
    p.add_argument("--allowed-gid", type=int)
    p.add_argument("--allowed-user")
    p.add_argument("--allowed-group")
    p.add_argument("--allowed-cgroup")
    a = p.parse_args(argv)
    uid = a.allowed_uid if a.allowed_uid is not None else pwd.getpwnam(a.allowed_user).pw_uid
    gid = a.allowed_gid if a.allowed_gid is not None else grp.getgrnam(a.allowed_group).gr_gid
    return run_server(
        a.state, a.socket, allowed_uid=uid, allowed_gid=gid, allowed_cgroup=a.allowed_cgroup
    )


if __name__ == "__main__":
    raise SystemExit(main())
