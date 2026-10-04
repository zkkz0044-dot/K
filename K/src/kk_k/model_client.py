from __future__ import annotations
import json, socket

ADDRESS = "/run/kk-model-ipc/model.sock"
ROLES = frozenset(
    {
        "K_CAPABILITY_PLAN",
        "SOUL_A_DIALOGUE",
        "SOUL_B_DIALOGUE",
        "SOUL_C_DIALOGUE",
        "MEDIA_PERCEPTION",
        "WORLD_A",
        "WORLD_B",
        "WORLD_C",
        "WORLD_CONTINUITY_A",
        "WORLD_CONTINUITY_B",
        "WORLD_CONTINUITY_C",
        "WORLD_THINK",
    }
)
MAX_PROMPT_BYTES = 65536
MAX_RESPONSE_BYTES = 16384
MAX_MEDIA_ITEMS = 12
MAX_IMAGE_DATA_CHARS = 2_200_000
MAX_FILE_DATA_CHARS = 42_500_000
MAX_AUDIO_DATA_CHARS = 28_000_000
MAX_MEDIA_CHARS = 55_000_000


class ModelClientError(RuntimeError):
    pass


def _strict(raw: bytes) -> dict:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ModelClientError("duplicate model response key")
            out[k] = v
        return out

    try:
        v = json.loads(raw.decode("utf-8"), object_pairs_hook=hook)
    except ModelClientError:
        raise
    except Exception as exc:
        raise ModelClientError("invalid model response JSON") from exc
    if not isinstance(v, dict):
        raise ModelClientError("model response object required")
    return v


def _clean_media(media: object) -> list[dict]:
    if media in (None, (), []):
        return []
    if not isinstance(media, (list, tuple)) or not (1 <= len(media) <= MAX_MEDIA_ITEMS):
        raise ModelClientError("invalid media list")
    out = []
    total = 0
    for item in media:
        if not isinstance(item, dict):
            raise ModelClientError("invalid media item")
        kind = item.get("kind")
        name = item.get("name", "attachment")
        if (
            not isinstance(name, str)
            or not name
            or len(name.encode("utf-8")) > 240
            or "\x00" in name
        ):
            raise ModelClientError("invalid media name")
        if kind == "image":
            data = item.get("data_url")
            source = item.get("source", "image")
            if (
                not isinstance(data, str)
                or not data.startswith("data:image/")
                or len(data) > MAX_IMAGE_DATA_CHARS
            ):
                raise ModelClientError("invalid image media")
            if source not in {"image", "video_frame"}:
                raise ModelClientError("invalid image source")
            clean = {"kind": "image", "name": name, "data_url": data, "source": source}
            if source == "video_frame" and isinstance(item.get("frame_time"), (int, float)):
                clean["frame_time"] = max(0.0, float(item["frame_time"]))
            total += len(data)
            out.append(clean)
        elif kind == "file":
            data = item.get("data_b64")
            mime = item.get("mime", "application/octet-stream")
            if not isinstance(data, str) or not data or len(data) > MAX_FILE_DATA_CHARS:
                raise ModelClientError("invalid file media")
            if not isinstance(mime, str) or not mime or len(mime) > 160:
                raise ModelClientError("invalid file mime")
            total += len(data)
            out.append({"kind": "file", "name": name, "mime": mime, "data_b64": data})
        elif kind == "audio":
            data = item.get("data_b64")
            mime = item.get("mime", "audio/mp4")
            if not isinstance(data, str) or not data or len(data) > MAX_AUDIO_DATA_CHARS:
                raise ModelClientError("invalid audio media")
            if not isinstance(mime, str) or not mime.startswith("audio/") or len(mime) > 160:
                raise ModelClientError("invalid audio mime")
            total += len(data)
            out.append({"kind": "audio", "name": name, "mime": mime, "data_b64": data})
        else:
            raise ModelClientError("invalid media kind")
        if total > MAX_MEDIA_CHARS:
            raise ModelClientError("media payload too large")
    return out


def call(role: str, prompt: str, *, address: str = ADDRESS, media=None) -> str:
    if role not in ROLES:
        raise ModelClientError("invalid model role")
    if not isinstance(prompt, str) or not (1 <= len(prompt.encode("utf-8")) <= MAX_PROMPT_BYTES):
        raise ModelClientError("invalid prompt")
    if address != ADDRESS:
        raise ModelClientError("fixed model socket required")
    clean = _clean_media(media)
    if role == "K_CAPABILITY_PLAN" and clean:
        raise ModelClientError("capability planning takes text context only")
    req = (
        {"schema": "K.MODEL.REQUEST.2", "role": role, "prompt": prompt, "media": clean}
        if clean
        else {"schema": "K.MODEL.REQUEST.1", "role": role, "prompt": prompt}
    )
    raw = (
        json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(125)
        sock.connect(address)
        sock.sendall(raw)
        buf = bytearray()
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > MAX_RESPONSE_BYTES:
                raise ModelClientError("model response too large")
    except OSError as exc:
        raise ModelClientError("model transport failed") from exc
    finally:
        sock.close()
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise ModelClientError("invalid model response frame")
    v = _strict(bytes(buf[:-1]))
    if frozenset(v) == {"schema", "reason_code"} and v.get("schema") == "K.MODEL.ERROR.1":
        if not isinstance(v.get("reason_code"), str):
            raise ModelClientError("invalid model error")
        raise ModelClientError("model gateway rejected: " + v["reason_code"])
    if frozenset(v) != {"schema", "provider_id", "trust", "text"}:
        raise ModelClientError("exact model response fields required")
    if (
        v["schema"] != "K.MODEL.RESPONSE.1"
        or not isinstance(v["provider_id"], str)
        or not v["provider_id"]
        or len(v["provider_id"]) > 96
        or v["trust"] != "UNTRUSTED"
    ):
        raise ModelClientError("model response identity/trust mismatch")
    text = v["text"]
    if not isinstance(text, str) or not (1 <= len(text.encode("utf-8")) <= 4096) or "\x00" in text:
        raise ModelClientError("invalid model output")
    if role == "K_CAPABILITY_PLAN":
        wrapped = {"schema": "K.CAPABILITY.PLAN.MODEL.1", "plan_text": text, "confidence": "LOW"}
    elif role == "SOUL_A_DIALOGUE":
        wrapped = {"schema": "FKP03.SOUL_A_DIALOGUE.1", "draft": text, "confidence": "LOW"}
    elif role == "WORLD_THINK":
        wrapped = {"schema": "K.WORLD.THINK.MODEL.1", "thought_text": text, "confidence": "LOW"}
    elif role == "WORLD_A":
        wrapped = {"schema": "K.WORLD.MODEL.A.1", "proposal_text": text, "confidence": "LOW"}
    elif role == "WORLD_CONTINUITY_A":
        wrapped = {
            "schema": "K.WORLD.CONTINUITY.MODEL.A.1",
            "proposal_text": text,
            "confidence": "LOW",
        }
    elif role in {"SOUL_B_DIALOGUE", "WORLD_B", "WORLD_CONTINUITY_B"}:
        low = text.lower()
        if text.strip().upper() == "OK":
            flags = ["NONE"]
        else:
            flags = []
            if "execution" in low or "execute" in low or "执行" in text:
                flags.append("EXECUTION_CONFUSION")
            if "authority" in low or "permission" in low or "权限" in text or "授权" in text:
                flags.append("AUTHORITY_CONFUSION")
            if "memory" in low or "记忆" in text:
                flags.append("MEMORY_CONFLICT")
            if not flags:
                flags = ["UNSUPPORTED_FACT"]
        wrapped = (
            {
                "schema": "FKP03.SOUL_B_DIALOGUE.1",
                "critique": text,
                "risk_flags": flags[:4],
                "confidence": "LOW",
            }
            if role == "SOUL_B_DIALOGUE"
            else (
                {
                    "schema": "K.WORLD.MODEL.B.1",
                    "critique": text,
                    "risk_flags": flags[:4],
                    "confidence": "LOW",
                }
                if role == "WORLD_B"
                else {
                    "schema": "K.WORLD.CONTINUITY.MODEL.B.1",
                    "critique": text,
                    "risk_flags": flags[:4],
                    "confidence": "LOW",
                }
            )
        )
    else:
        verdict = text.strip().upper()
        if verdict not in {"APPROVE_A", "REJECT_A"}:
            raise ModelClientError("invalid C verdict token")
        wrapped = (
            {
                "schema": "FKP03.SOUL_C_DIALOGUE.1",
                "answer": verdict,
                "confidence": "LOW",
                "response_type": "ANSWER" if verdict == "APPROVE_A" else "DECLINE",
            }
            if role == "SOUL_C_DIALOGUE"
            else (
                {"schema": "K.WORLD.MODEL.C.1", "verdict": verdict, "confidence": "LOW"}
                if role == "WORLD_C"
                else {
                    "schema": "K.WORLD.CONTINUITY.MODEL.C.1",
                    "verdict": verdict,
                    "confidence": "LOW",
                }
            )
        )
    return json.dumps(wrapped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
