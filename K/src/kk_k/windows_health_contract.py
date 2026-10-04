"""Strict contract for future Windows read-only health bridge."""

from __future__ import annotations
import re

REQ_SCHEMA = "K.WINDOWS.HEALTH.REQUEST.1"
RECEIPT_SCHEMA = "K.WINDOWS.HEALTH.RECEIPT.1"
_HOST = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class WindowsHealthError(ValueError):
    pass


def parse_request(value: object) -> str:
    if not isinstance(value, dict) or set(value) != {"schema", "host"}:
        raise WindowsHealthError("exact windows health request fields required")
    if value.get("schema") != REQ_SCHEMA:
        raise WindowsHealthError("invalid windows health schema")
    host = value.get("host")
    if not isinstance(host, str) or _HOST.fullmatch(host) is None:
        raise WindowsHealthError("invalid windows host id")
    return host


def verify_receipt(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema", "host", "status", "data"}:
        raise WindowsHealthError("exact windows receipt fields required")
    if value.get("schema") != RECEIPT_SCHEMA or value.get("status") != "PASS":
        raise WindowsHealthError("invalid windows health envelope")
    data = value.get("data")
    required = {"os", "hostname", "uptime_seconds", "cpu_percent", "memory", "disk_system", "agent"}
    if not isinstance(data, dict) or set(data) != required:
        raise WindowsHealthError("invalid windows health data")
    if data["os"] != "windows" or not isinstance(data["hostname"], str):
        raise WindowsHealthError("invalid windows identity")
    if type(data["uptime_seconds"]) is not int or data["uptime_seconds"] < 0:
        raise WindowsHealthError("invalid uptime")
    cpu = data["cpu_percent"]
    if not isinstance(cpu, (int, float)) or isinstance(cpu, bool) or not (0 <= cpu <= 100):
        raise WindowsHealthError("invalid cpu")
    for key in ("memory", "disk_system"):
        obj = data[key]
        if not isinstance(obj, dict) or set(obj) != {"total_bytes", "free_bytes"}:
            raise WindowsHealthError("invalid capacity data")
        if type(obj["total_bytes"]) is not int or type(obj["free_bytes"]) is not int:
            raise WindowsHealthError("invalid capacity type")
        if obj["total_bytes"] < 0 or not (0 <= obj["free_bytes"] <= obj["total_bytes"]):
            raise WindowsHealthError("invalid capacity values")
    agent = data["agent"]
    if not isinstance(agent, dict) or set(agent) != {"protocol", "version", "read_only"}:
        raise WindowsHealthError("invalid windows agent")
    if agent["protocol"] != "KK.WINDOWS.HEALTH.1" or agent["read_only"] is not True:
        raise WindowsHealthError("windows agent is not approved read-only protocol")
    if not isinstance(agent["version"], str) or not agent["version"]:
        raise WindowsHealthError("invalid windows agent version")
    return dict(data)


def unavailable_receipt(host: str) -> dict:
    return {
        "schema": RECEIPT_SCHEMA,
        "host": host,
        "status": "VETO",
        "reason_code": "WINDOWS_BRIDGE_UNAVAILABLE",
    }
