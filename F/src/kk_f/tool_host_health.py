"""F-owned, fixed read-only VPS health adapter. No shell, network, or caller parameters."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

SCHEMA = "F.TOOL.HOST_HEALTH.1"
PROC_UPTIME = Path("/proc/uptime")
PROC_MEMINFO = Path("/proc/meminfo")
ROOT_FS = "/"


class HostHealthError(RuntimeError):
    pass


def _read_uptime_seconds(path: Path = PROC_UPTIME) -> int:
    try:
        first = path.read_text(encoding="ascii").split()[0]
        value = int(float(first))
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        raise HostHealthError("uptime unavailable") from exc
    if value < 0:
        raise HostHealthError("invalid uptime")
    return value


def _read_meminfo(path: Path = PROC_MEMINFO) -> tuple[int, int]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise HostHealthError("meminfo unavailable") from exc
    values = {}
    for line in lines:
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        if key not in {"MemTotal", "MemAvailable"}:
            continue
        parts = rest.strip().split()
        if not parts:
            raise HostHealthError("invalid meminfo")
        try:
            kib = int(parts[0])
        except ValueError as exc:
            raise HostHealthError("invalid meminfo") from exc
        if kib < 0:
            raise HostHealthError("invalid meminfo")
        values[key] = kib * 1024
    if set(values) != {"MemTotal", "MemAvailable"}:
        raise HostHealthError("required meminfo missing")
    return values["MemTotal"], values["MemAvailable"]


def collect_host_health() -> dict:
    try:
        load1, load5, load15 = os.getloadavg()
        disk = shutil.disk_usage(ROOT_FS)
    except (OSError, ValueError) as exc:
        raise HostHealthError("host metrics unavailable") from exc
    total_mem, available_mem = _read_meminfo()
    uptime = _read_uptime_seconds()
    cpu_count = os.cpu_count() or 1
    if cpu_count < 1:
        raise HostHealthError("invalid cpu count")
    return {
        "schema": SCHEMA,
        "uptime_seconds": uptime,
        "cpu_count": cpu_count,
        "load": {
            "one": round(float(load1), 3),
            "five": round(float(load5), 3),
            "fifteen": round(float(load15), 3),
        },
        "memory": {
            "total_bytes": total_mem,
            "available_bytes": available_mem,
        },
        "disk_root": {
            "total_bytes": int(disk.total),
            "free_bytes": int(disk.free),
        },
    }
