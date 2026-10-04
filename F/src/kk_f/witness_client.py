"""FH03 unprivileged strict client for the local monotonic witness."""

from __future__ import annotations

import json
import socket

MAX_RESPONSE = 8192


class WitnessClientError(RuntimeError):
    pass


def _request(socket_path: str, payload: dict) -> None:
    if not isinstance(socket_path, str) or not socket_path.startswith("/") or "\x00" in socket_path:
        raise WitnessClientError("absolute witness socket path required")
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        + b"\n"
    )
    if len(raw) > 4096:
        raise WitnessClientError("witness request too large")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(2.0)
        client.connect(socket_path)
        client.sendall(raw)
        chunks = []
        total = 0
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE:
                raise WitnessClientError("witness response too large")
            chunks.append(chunk)
            if b"\n" in chunk:
                break
    except OSError as exc:
        raise WitnessClientError("witness unavailable") from exc
    finally:
        client.close()
    try:
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WitnessClientError("invalid witness response") from exc
    if value == {"ok": True}:
        return
    if (
        isinstance(value, dict)
        and frozenset(value) == frozenset({"ok", "error"})
        and value.get("ok") is False
        and isinstance(value.get("error"), str)
    ):
        raise WitnessClientError(value["error"])
    raise WitnessClientError("unexpected witness response")


def verify(socket_path: str, channel: str, generation: int, digest: str) -> None:
    _request(
        socket_path,
        {"op": "verify", "channel": channel, "generation": generation, "digest": digest},
    )


def prepare(
    socket_path: str,
    channel: str,
    current_generation: int,
    current_digest: str,
    new_generation: int,
    new_digest: str,
) -> None:
    _request(
        socket_path,
        {
            "op": "prepare",
            "channel": channel,
            "current_generation": current_generation,
            "current_digest": current_digest,
            "new_generation": new_generation,
            "new_digest": new_digest,
        },
    )


def commit(socket_path: str, channel: str, generation: int, digest: str) -> None:
    _request(
        socket_path,
        {"op": "commit", "channel": channel, "generation": generation, "digest": digest},
    )


def recover(socket_path: str, channel: str, generation: int, digest: str) -> None:
    _request(
        socket_path,
        {"op": "recover", "channel": channel, "generation": generation, "digest": digest},
    )
