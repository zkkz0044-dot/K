from __future__ import annotations
from dataclasses import dataclass
import re

MAX_IMAGES = 6
MAX_FILES = 5
MAX_IMAGE_DATA_URL = 2_000_000
MAX_FILE_BYTES = 30_000_000
UPLOAD_PREFIX = "/run/kk-uploads/"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX32 = re.compile(r"^[0-9a-f]{32}$")


class MediaIngressError(ValueError):
    pass


@dataclass(frozen=True)
class MediaAttachment:
    kind: str
    name: str
    mime: str
    source: str
    size: int
    sha256: str
    data_url: str = ""
    upload_path: str = ""
    upload_id: str = ""


def _clean_text(v: object, label: str, max_len: int) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > max_len or "\x00" in v:
        raise MediaIngressError("invalid " + label)
    return v.strip()


def validate_attachments(raw: object) -> tuple[MediaAttachment, ...]:
    if raw in (None, []):
        return ()
    if not isinstance(raw, list):
        raise MediaIngressError("attachments must be list")
    out = []
    images = 0
    files = 0
    for item in raw:
        if not isinstance(item, dict):
            raise MediaIngressError("attachment object required")
        kind = item.get("kind")
        name = _clean_text(item.get("name"), "attachment name", 180)
        mime = _clean_text(item.get("mime"), "attachment mime", 120)
        source = _clean_text(item.get("source"), "attachment source", 40)
        size = item.get("size")
        sha = item.get("sha256")
        if not isinstance(size, int) or size < 0:
            raise MediaIngressError("invalid attachment size")
        if not isinstance(sha, str) or not HEX64.fullmatch(sha):
            raise MediaIngressError("invalid attachment sha256")
        if kind == "image":
            images += 1
            if images > MAX_IMAGES:
                raise MediaIngressError("too many image inputs")
            data = _clean_text(item.get("data_url"), "image data", MAX_IMAGE_DATA_URL)
            if not data.startswith(
                ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
            ):
                raise MediaIngressError("unsupported image data")
            if source not in {"image", "video_frame"}:
                raise MediaIngressError("invalid image source")
            out.append(MediaAttachment(kind, name, mime, source, size, sha, data_url=data))
        elif kind == "file":
            files += 1
            if files > MAX_FILES or size > MAX_FILE_BYTES:
                raise MediaIngressError("invalid file limit")
            upload_id = _clean_text(item.get("upload_id"), "upload id", 32)
            if not HEX32.fullmatch(upload_id):
                raise MediaIngressError("invalid upload id")
            path = _clean_text(item.get("upload_path"), "upload path", 200)
            if path != UPLOAD_PREFIX + upload_id + ".bin":
                raise MediaIngressError("invalid upload path")
            out.append(
                MediaAttachment(
                    kind, name, mime, "file", size, sha, upload_path=path, upload_id=upload_id
                )
            )
        else:
            raise MediaIngressError("unsupported attachment kind")
    return tuple(out)


def public_metadata(items: tuple[MediaAttachment, ...]) -> list[dict]:
    return [
        {
            "kind": x.kind,
            "name": x.name,
            "mime": x.mime,
            "source": x.source,
            "size": x.size,
            "sha256": x.sha256,
        }
        for x in items
    ]


def model_payload(items: tuple[MediaAttachment, ...]) -> list[dict]:
    out = []
    for x in items:
        if x.kind == "image":
            out.append(
                {
                    "kind": "image",
                    "name": x.name,
                    "mime": x.mime,
                    "source": x.source,
                    "data_url": x.data_url,
                }
            )
        else:
            out.append(
                {
                    "kind": "file",
                    "name": x.name,
                    "mime": x.mime,
                    "source": "file",
                    "path": x.upload_path,
                    "size": x.size,
                }
            )
    return out
