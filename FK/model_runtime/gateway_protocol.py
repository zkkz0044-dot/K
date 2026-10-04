from __future__ import annotations

import json
import socket

MAX_REQUEST = 64_000_000
MAX_RESPONSE = 16384
MAX_PROMPT = 65536
CLOUD_RELAY_TIMEOUT_SECONDS = 125
LOCAL_RELAY_TIMEOUT_SECONDS = 125
DIALOGUE_ROLES = frozenset(
    {"K_CAPABILITY_PLAN", "SOUL_A_DIALOGUE", "SOUL_B_DIALOGUE", "SOUL_C_DIALOGUE"}
)
WORLD_ROLES = frozenset({"WORLD_A", "WORLD_B", "WORLD_C"})
CONTINUITY_ROLES = frozenset({"WORLD_CONTINUITY_A", "WORLD_CONTINUITY_B", "WORLD_CONTINUITY_C"})
THINK_ROLES = frozenset({"WORLD_THINK"})
COGNITION_ROLES = WORLD_ROLES | CONTINUITY_ROLES | THINK_ROLES
ROLES = DIALOGUE_ROLES | COGNITION_ROLES


class GatewayError(RuntimeError):
    pass


def _validate_media(media: object) -> list[dict]:
    if not isinstance(media, list) or not (1 <= len(media) <= 12):
        raise GatewayError("INVALID_MEDIA")
    out = []
    total = 0
    for item in media:
        if not isinstance(item, dict):
            raise GatewayError("INVALID_MEDIA")
        kind = item.get("kind")
        name = item.get("name")
        if (
            not isinstance(name, str)
            or not name
            or len(name.encode("utf-8")) > 240
            or "\x00" in name
        ):
            raise GatewayError("INVALID_MEDIA_NAME")
        if kind == "image":
            allowed = {"kind", "name", "data_url", "source", "frame_time"}
            if not set(item).issubset(allowed):
                raise GatewayError("INVALID_MEDIA_FIELDS")
            data = item.get("data_url")
            source = item.get("source", "image")
            if (
                not isinstance(data, str)
                or not data.startswith("data:image/")
                or len(data) > 2_200_000
            ):
                raise GatewayError("INVALID_IMAGE_MEDIA")
            if source not in {"image", "video_frame"}:
                raise GatewayError("INVALID_IMAGE_SOURCE")
            clean = {"kind": "image", "name": name, "data_url": data, "source": source}
            if source == "video_frame" and isinstance(item.get("frame_time"), (int, float)):
                clean["frame_time"] = max(0.0, float(item["frame_time"]))
            total += len(data)
            out.append(clean)
        elif kind == "file":
            if set(item) != {"kind", "name", "mime", "data_b64"}:
                raise GatewayError("INVALID_MEDIA_FIELDS")
            data = item.get("data_b64")
            mime = item.get("mime")
            if not isinstance(data, str) or not data or len(data) > 42_500_000:
                raise GatewayError("INVALID_FILE_MEDIA")
            if not isinstance(mime, str) or not mime or len(mime) > 160:
                raise GatewayError("INVALID_FILE_MIME")
            total += len(data)
            out.append({"kind": "file", "name": name, "mime": mime, "data_b64": data})
        elif kind == "audio":
            if set(item) != {"kind", "name", "mime", "data_b64"}:
                raise GatewayError("INVALID_MEDIA_FIELDS")
            data = item.get("data_b64")
            mime = item.get("mime")
            if not isinstance(data, str) or not data or len(data) > 28_000_000:
                raise GatewayError("INVALID_AUDIO_MEDIA")
            if not isinstance(mime, str) or not mime.startswith("audio/") or len(mime) > 160:
                raise GatewayError("INVALID_AUDIO_MIME")
            total += len(data)
            out.append({"kind": "audio", "name": name, "mime": mime, "data_b64": data})
        else:
            raise GatewayError("INVALID_MEDIA_KIND")
        if total > 55_000_000:
            raise GatewayError("MEDIA_TOO_LARGE")
    return out


def strict_json(raw: bytes) -> dict:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise GatewayError("DUPLICATE_KEY")
            out[k] = v
        return out

    try:
        v = json.loads(raw.decode("utf-8"), object_pairs_hook=hook)
    except GatewayError:
        raise
    except Exception as exc:
        raise GatewayError("INVALID_JSON") from exc
    if not isinstance(v, dict):
        raise GatewayError("EXACT_FIELDS_REQUIRED")
    if v.get("schema") == "K.MODEL.REQUEST.1":
        if frozenset(v) != {"schema", "role", "prompt"}:
            raise GatewayError("EXACT_FIELDS_REQUIRED")
        v["media"] = []
    elif v.get("schema") == "K.MODEL.REQUEST.2":
        if frozenset(v) != {"schema", "role", "prompt", "media"}:
            raise GatewayError("EXACT_FIELDS_REQUIRED")
        v["media"] = _validate_media(v["media"])
    else:
        raise GatewayError("INVALID_REQUEST_SCHEMA")
    if v["role"] not in ROLES:
        raise GatewayError("INVALID_REQUEST_SCHEMA")
    if v["role"] == "K_CAPABILITY_PLAN" and v["media"]:
        raise GatewayError("CAPABILITY_MEDIA_DENIED")
    if not isinstance(v["prompt"], str) or not (1 <= len(v["prompt"].encode()) <= MAX_PROMPT):
        raise GatewayError("INVALID_PROMPT")
    return v


def recv_line(conn: socket.socket) -> bytes:
    buf = bytearray()
    while b"\n" not in buf:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_REQUEST:
            raise GatewayError("REQUEST_TOO_LARGE")
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise GatewayError("INVALID_FRAME")
    return bytes(buf[:-1])


