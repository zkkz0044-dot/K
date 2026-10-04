"""FK01/FK02 F-owned local gateway. No external network, no caller-controlled process spec."""

from __future__ import annotations

import json
import os
import socket
import stat
from typing import Callable

from .path_guard import PathGuardError, open_absolute_file, read_all_fd
from .frozen_authority import FrozenAuthorityError, authorize_process, load_frozen_authority
from .process_preflight import ProcessPreflightError, verify_process_candidate
from .process_executor import ProcessExecutionError, execute_and_wait
from .fk_peer_identity import (
    FKPeerIdentityError,
    authorize_peer,
    cgroup_contains_unit,
    peer_credentials,
)
from .fk_approval import APPROVAL_PATH, FKApprovalError, consume_a03_approval

REQUEST_SCHEMA = "FK01.REQUEST.1"
RECEIPT_SCHEMA = "FK01.F_RECEIPT.1"
ERROR_SCHEMA = "FK01.ERROR.1"
DEFAULT_ADDRESS = "\0kk-fk-v1"
F_STATE_PATH = "/root/K/F/PROJECT_STATE.json"
AUDIT_LOG_PATH = "/root/K/F/evidence/fk/decision_markers.jsonl"
A03_AUTHORITY_PATH = "/root/K/F/fk_actions/a03_authority.json"
A03_EXPECTED_EXECUTABLE = "/root/K/F/fk_actions/a03_smoke.py"
MAX_REQUEST_BYTES = 1024
MAX_RESPONSE_BYTES = 4096
MAX_STATE_BYTES = 65536
REQUEST_KEYS = frozenset({"schema", "action_id"})

# FKP04: A03 is live only through the F-owned single-use human approval gate.
ENABLED_ACTIONS = frozenset(
    {
        "A01_READ_PROJECT_STATE",
        "A02_READ_F_STATUS",
        "A03_RUN_F_SMOKE_TEST",
        "A04_WRITE_K_DECISION_LOG",
        "A05_NO_ACTION",
    }
)
KNOWN_ACTIONS = frozenset(
    {
        "A01_READ_PROJECT_STATE",
        "A02_READ_F_STATUS",
        "A03_RUN_F_SMOKE_TEST",
        "A04_WRITE_K_DECISION_LOG",
        "A05_NO_ACTION",
    }
)


class FKGatewayError(ValueError):
    pass


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FKGatewayError("duplicate JSON key")
        out[key] = value
    return out


def _strict_object(raw: str) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=_strict_pairs)
    except FKGatewayError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise FKGatewayError("invalid request JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != REQUEST_KEYS:
        raise FKGatewayError("exact request fields required")
    if value["schema"] != REQUEST_SCHEMA:
        raise FKGatewayError("unsupported request schema")
    if not isinstance(value["action_id"], str) or value["action_id"] not in KNOWN_ACTIONS:
        raise FKGatewayError("unknown action_id")
    return value


def parse_request(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REQUEST_BYTES:
        raise FKGatewayError("invalid request size")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FKGatewayError("request must be UTF-8") from exc
    return _strict_object(text)


def _veto(action_id: str, reason_code: str, stage: str) -> dict:
    return {
        "schema": RECEIPT_SCHEMA,
        "action_id": action_id,
        "outcome": "VETO",
        "evidence": {
            "kind": "VETO",
            "reason_code": reason_code,
            "validation_stage": stage,
        },
    }


def _load_authoritative_state() -> dict:
    fd = -1
    try:
        fd = open_absolute_file(F_STATE_PATH)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise FKGatewayError("F state must be regular file")
        if info.st_uid != 0:
            raise FKGatewayError("F state must be root-owned")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise FKGatewayError("F state must not be group/world writable")
        raw = read_all_fd(fd, max_bytes=MAX_STATE_BYTES)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FKGatewayError("F state must be UTF-8") from exc
        try:
            value = json.loads(text, object_pairs_hook=_strict_pairs)
        except FKGatewayError:
            raise
        except (json.JSONDecodeError, TypeError) as exc:
            raise FKGatewayError("F state invalid JSON") from exc
        if not isinstance(value, dict):
            raise FKGatewayError("F state must be object")
        for field in ("status", "current_phase", "final_acceptance"):
            if (
                field not in value
                or not isinstance(value[field], str)
                or not (1 <= len(value[field]) <= 64)
            ):
                raise FKGatewayError("F state required field invalid")
        return {
            "status": value["status"],
            "current_phase": value["current_phase"],
            "final_acceptance": value["final_acceptance"],
        }
    except (PathGuardError, OSError) as exc:
        raise FKGatewayError("F state inaccessible") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def _run_a03_static() -> dict:
    """Run only the F-owned, Frozen-Authority-bound A03 smoke candidate.

    This function is intentionally not exposed by FK01/FK02/FK03 network policy yet.
    """
    try:
        manifest = load_frozen_authority(A03_AUTHORITY_PATH)
        spec = manifest["process_spec"]
        if manifest["authority_id"] != "fk-a03-smoke":
            return _veto("A03_RUN_F_SMOKE_TEST", "AUTHORITY_MISMATCH", "FROZEN_AUTHORITY")
        if (
            spec.get("executable") != A03_EXPECTED_EXECUTABLE
            or spec.get("cwd") != "/root/K/F"
            or spec.get("argv") != []
            or spec.get("env") != {}
        ):
            return _veto("A03_RUN_F_SMOKE_TEST", "AUTHORITY_MISMATCH", "FROZEN_AUTHORITY")
        authorize_process(A03_AUTHORITY_PATH, spec)
    except FrozenAuthorityError:
        return _veto("A03_RUN_F_SMOKE_TEST", "AUTHORITY_MISMATCH", "FROZEN_AUTHORITY")

    try:
        verify_process_candidate(spec)
    except ProcessPreflightError as exc:
        reason = (
            "EXECUTABLE_SHA256_MISMATCH"
            if str(exc) == "executable SHA-256 mismatch"
            else "PRECHECK_FAILED"
        )
        return _veto("A03_RUN_F_SMOKE_TEST", reason, "PROCESS_PREFLIGHT")

    try:
        result = execute_and_wait(spec, timeout_seconds=5)
    except ProcessExecutionError:
        return _veto("A03_RUN_F_SMOKE_TEST", "PROCESS_EXECUTION_FAILED", "PROCESS_EXECUTOR")

    failed = 0 if result["exit_code"] == 0 and result["timed_out"] is False else 1
    return {
        "schema": RECEIPT_SCHEMA,
        "action_id": "A03_RUN_F_SMOKE_TEST",
        "outcome": "EXECUTED",
        "evidence": {"kind": "F_SMOKE", "exit_code": result["exit_code"], "tests_failed": failed},
    }


def _run_a03_approved(*, now_epoch: int | None = None, approval_path: str = APPROVAL_PATH) -> dict:
    """Privileged path: F-owned approval is the sole execution authority."""
    try:
        allowed, reason, _approval = consume_a03_approval(now_epoch=now_epoch, path=approval_path)
    except FKApprovalError:
        return _veto("A03_RUN_F_SMOKE_TEST", "HUMAN_APPROVAL_INVALID", "HUMAN_APPROVAL")
    if not allowed:
        return _veto("A03_RUN_F_SMOKE_TEST", reason, "HUMAN_APPROVAL")
    return _run_a03_static()


def _append_fixed_decision_marker() -> None:
    fd = -1
    try:
        fd = open_absolute_file(AUDIT_LOG_PATH, flags=os.O_WRONLY | os.O_APPEND)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise FKGatewayError("audit log must be regular file")
        if info.st_uid != 0:
            raise FKGatewayError("audit log must be root-owned")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise FKGatewayError("audit log must not be group/world writable")
        record = {
            "schema": "FK03.A04.1",
            "action_id": "A04_WRITE_K_DECISION_LOG",
            "marker": "K_DECISION_ACCEPTED",
        }
        raw = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        written = os.write(fd, raw)
        if written != len(raw):
            raise FKGatewayError("short audit append")
        os.fsync(fd)
    except (PathGuardError, OSError) as exc:
        raise FKGatewayError("audit log inaccessible") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def dispatch(action_id: str, *, peer_uid: int, allowed_uid: int) -> dict:
    if peer_uid != allowed_uid:
        return _veto(action_id, "PEER_AUTH_DENY", "PEER_AUTH")
    if action_id not in ENABLED_ACTIONS:
        return _veto(action_id, "ACTION_DISABLED", "FK_POLICY")
    if action_id == "A03_RUN_F_SMOKE_TEST":
        return _run_a03_approved()
    if action_id == "A05_NO_ACTION":
        return {
            "schema": RECEIPT_SCHEMA,
            "action_id": action_id,
            "outcome": "EXECUTED",
            "evidence": {"kind": "NO_ACTION", "process_started": False},
        }
    if action_id == "A04_WRITE_K_DECISION_LOG":
        try:
            _append_fixed_decision_marker()
        except FKGatewayError:
            return _veto(action_id, "AUDIT_LOG_INVALID", "F_AUDIT")
        return {
            "schema": RECEIPT_SCHEMA,
            "action_id": action_id,
            "outcome": "EXECUTED",
            "evidence": {"kind": "K_DECISION_LOG", "appended": True, "durable": True},
        }
    if action_id in {"A01_READ_PROJECT_STATE", "A02_READ_F_STATUS"}:
        try:
            state = _load_authoritative_state()
        except FKGatewayError:
            return _veto(action_id, "F_STATE_INVALID", "F_STATE")
        if action_id == "A01_READ_PROJECT_STATE":
            evidence = {"kind": "PROJECT_STATE", "status": state["current_phase"]}
        else:
            evidence = {"kind": "F_STATUS", "status": state["status"]}
        return {
            "schema": RECEIPT_SCHEMA,
            "action_id": action_id,
            "outcome": "EXECUTED",
            "evidence": evidence,
        }
    return _veto(action_id, "ACTION_DISABLED", "FK_POLICY")


def _recv_line(conn: socket.socket) -> bytes:
    buf = bytearray()
    while True:
        chunk = conn.recv(min(256, MAX_REQUEST_BYTES + 1 - len(buf)))
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_REQUEST_BYTES:
            raise FKGatewayError("request too large")
        if b"\n" in chunk:
            break
    if not buf.endswith(b"\n"):
        raise FKGatewayError("unterminated request")
    raw = bytes(buf[:-1])
    if b"\n" in raw:
        raise FKGatewayError("multiple request frames")
    return raw


def _send(conn: socket.socket, value: dict) -> None:
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FKGatewayError("response too large")
    conn.sendall(raw)


def _peer_uid(conn: socket.socket) -> int:
    try:
        return peer_credentials(conn)[1]
    except FKPeerIdentityError as exc:
        raise FKGatewayError("peer credentials unavailable") from exc


def handle_connection(
    conn: socket.socket, *, allowed_uid: int | None = None, allowed_cgroup_unit: str | None = None
) -> None:
    try:
        pid, peer_uid, _gid = peer_credentials(conn)
        request = parse_request(_recv_line(conn))
        try:
            authorized = authorize_peer(
                pid=pid,
                uid=peer_uid,
                allowed_uid=allowed_uid,
                allowed_cgroup_unit=allowed_cgroup_unit,
            )
        except FKPeerIdentityError:
            authorized = False
        if not authorized:
            _send(conn, _veto(request["action_id"], "PEER_AUTH_DENY", "PEER_AUTH"))
            return
        _send(conn, dispatch(request["action_id"], peer_uid=peer_uid, allowed_uid=peer_uid))
    except (FKGatewayError, FKPeerIdentityError):
        _send(
            conn,
            {"schema": ERROR_SCHEMA, "reason_code": "INVALID_REQUEST", "stage": "REQUEST_PARSE"},
        )


def _validate_peer_policy(
    allowed_uid: int | None, allowed_cgroup_unit: str | None
) -> tuple[int | None, str | None]:
    if allowed_uid is None and allowed_cgroup_unit is None:
        allowed_uid = os.getuid()
    if allowed_uid is not None and allowed_cgroup_unit is not None:
        raise FKGatewayError("ambiguous peer policy")
    if allowed_uid is not None and (type(allowed_uid) is not int or allowed_uid < 0):
        raise FKGatewayError("invalid allowed_uid")
    if allowed_cgroup_unit is not None:
        try:
            cgroup_contains_unit("", allowed_cgroup_unit)
        except FKPeerIdentityError as exc:
            raise FKGatewayError("invalid allowed_cgroup_unit") from exc
    return allowed_uid, allowed_cgroup_unit


def serve_once(
    *,
    address: str = DEFAULT_ADDRESS,
    allowed_uid: int | None = None,
    allowed_cgroup_unit: str | None = None,
    ready: Callable[[], None] | None = None,
) -> None:
    allowed_uid, allowed_cgroup_unit = _validate_peer_policy(allowed_uid, allowed_cgroup_unit)
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKGatewayError("abstract AF_UNIX address required")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(address)
        server.listen(4)
        if ready is not None:
            ready()
        conn, _ = server.accept()
        with conn:
            handle_connection(
                conn, allowed_uid=allowed_uid, allowed_cgroup_unit=allowed_cgroup_unit
            )
    finally:
        server.close()


def serve_forever(
    *,
    address: str = DEFAULT_ADDRESS,
    allowed_uid: int | None = None,
    allowed_cgroup_unit: str | None = None,
) -> None:
    """Persistent F gateway for the currently enabled safe FK action set."""
    allowed_uid, allowed_cgroup_unit = _validate_peer_policy(allowed_uid, allowed_cgroup_unit)
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKGatewayError("abstract AF_UNIX address required")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(address)
        server.listen(16)
        while True:
            conn, _ = server.accept()
            with conn:
                handle_connection(
                    conn, allowed_uid=allowed_uid, allowed_cgroup_unit=allowed_cgroup_unit
                )
    finally:
        server.close()
