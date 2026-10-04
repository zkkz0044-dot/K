"""F-side client to isolated network search worker. F tool gateway itself stays AF_UNIX-only."""

from __future__ import annotations
import json, socket

ADDRESS = "\0kk-cap-search-v1"
MAX_RESPONSE = 8192


class WebSearchError(RuntimeError):
    pass


def search_web(query: object) -> dict:
    if (
        not isinstance(query, str)
        or not (1 <= len(query) <= 200)
        or any(ord(c) < 32 for c in query)
    ):
        raise WebSearchError("invalid query")
    req = (
        json.dumps(
            {"schema": "KK.CAP.SEARCH.1", "query": query}, ensure_ascii=False, separators=(",", ":")
        )
        + "\n"
    ).encode()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(30)
    try:
        s.connect(ADDRESS)
        s.sendall(req)
        buf = bytearray()
        while True:
            x = s.recv(2048)
            if not x:
                break
            buf.extend(x)
            if len(buf) > MAX_RESPONSE:
                raise WebSearchError("oversize")
            if b"\n" in x:
                break
    except (OSError, socket.timeout) as exc:
        raise WebSearchError("worker unavailable") from exc
    finally:
        s.close()
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise WebSearchError("bad frame")
    try:
        v = json.loads(bytes(buf[:-1]).decode("utf-8"))
    except Exception as exc:
        raise WebSearchError("bad json") from exc
    if (
        not isinstance(v, dict)
        or set(v) != {"schema", "status", "results"}
        or v.get("schema") != "KK.CAP.SEARCH.RECEIPT.1"
        or v.get("status") != "PASS"
        or not isinstance(v.get("results"), list)
    ):
        raise WebSearchError("bad receipt")
    out = []
    for item in v["results"][:3]:
        if not isinstance(item, dict) or set(item) != {"title", "url", "snippet"}:
            raise WebSearchError("bad item")
        if not all(isinstance(item[k], str) for k in ("title", "url", "snippet")) or not item[
            "url"
        ].startswith(("http://", "https://")):
            raise WebSearchError("bad item")
        out.append(
            {
                "title": item["title"][:200],
                "url": item["url"][:500],
                "snippet": item["snippet"][:400],
            }
        )
    return {"schema": "F.TOOL.WEB_SEARCH.1", "query": query, "results": out}
