"""Persistent file queue for external connector broker requests/results."""

from __future__ import annotations
import json, os, re, secrets, tempfile, time
from pathlib import Path
from .connector_broker import ConnectorBrokerError, parse_request, verify_receipt

QUEUE_ROOT = Path("/root/K/FK/connector_broker")
REQUESTS = QUEUE_ROOT / "requests"
RESULTS = QUEUE_ROOT / "results"
ARCHIVE = QUEUE_ROOT / "archive"
REQ_ENV_SCHEMA = "K.CONNECTOR.QUEUE.REQUEST.1"
RES_ENV_SCHEMA = "K.CONNECTOR.QUEUE.RESULT.1"
ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ConnectorQueueError(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        raw = (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        ).encode()
        os.fchmod(fd, 0o600)
        os.write(fd, raw)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, path)
    finally:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)


def enqueue(request: dict, *, now: int | None = None, request_id: str | None = None) -> dict:
    parsed = parse_request(request)
    rid = secrets.token_hex(16) if request_id is None else request_id
    if not isinstance(rid, str) or ID_RE.fullmatch(rid) is None:
        raise ConnectorQueueError("invalid request id")
    ts = int(time.time()) if now is None else now
    if type(ts) is not int or ts < 0:
        raise ConnectorQueueError("invalid created_at")
    env = {"schema": REQ_ENV_SCHEMA, "request_id": rid, "created_at": ts, "request": request}
    path = REQUESTS / (rid + ".json")
    if path.exists() or (RESULTS / (rid + ".json")).exists():
        raise ConnectorQueueError("request id collision")
    _atomic_json(path, env)
    return {"request_id": rid, "tool": parsed.tool, "path": str(path)}


def read_pending(request_id: str) -> dict:
    if not isinstance(request_id, str) or ID_RE.fullmatch(request_id) is None:
        raise ConnectorQueueError("invalid request id")
    path = REQUESTS / (request_id + ".json")
    try:
        env = json.loads(path.read_text())
    except Exception as exc:
        raise ConnectorQueueError("request unavailable") from exc
    if (
        not isinstance(env, dict)
        or set(env) != {"schema", "request_id", "created_at", "request"}
        or env.get("schema") != REQ_ENV_SCHEMA
        or env.get("request_id") != request_id
    ):
        raise ConnectorQueueError("invalid queued request")
    parse_request(env["request"])
    return env


def write_result(request_id: str, receipt: dict, *, now: int | None = None) -> dict:
    env = read_pending(request_id)
    tool = parse_request(env["request"]).tool
    verify_receipt(tool, receipt)
    ts = int(time.time()) if now is None else now
    if type(ts) is not int or ts < env["created_at"]:
        raise ConnectorQueueError("invalid completed_at")
    out = {
        "schema": RES_ENV_SCHEMA,
        "request_id": request_id,
        "completed_at": ts,
        "receipt": receipt,
    }
    path = RESULTS / (request_id + ".json")
    if path.exists():
        raise ConnectorQueueError("result already exists")
    _atomic_json(path, out)
    return {"request_id": request_id, "tool": tool, "path": str(path)}


def consume(request_id: str) -> dict:
    env = read_pending(request_id)
    tool = parse_request(env["request"]).tool
    rpath = RESULTS / (request_id + ".json")
    try:
        result = json.loads(rpath.read_text())
    except Exception as exc:
        raise ConnectorQueueError("result unavailable") from exc
    if (
        not isinstance(result, dict)
        or set(result) != {"schema", "request_id", "completed_at", "receipt"}
        or result.get("schema") != RES_ENV_SCHEMA
        or result.get("request_id") != request_id
    ):
        raise ConnectorQueueError("invalid queued result")
    verified = verify_receipt(tool, result["receipt"])
    dst = ARCHIVE / (request_id + ".request.json")
    rdst = ARCHIVE / (request_id + ".result.json")
    if dst.exists() or rdst.exists():
        raise ConnectorQueueError("archive collision")
    os.replace(REQUESTS / (request_id + ".json"), dst)
    os.replace(rpath, rdst)
    return {"request_id": request_id, "tool": tool, "verified": True, "data": verified}
