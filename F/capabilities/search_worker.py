#!/usr/bin/python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request
import time
import xml.etree.ElementTree as ET

ADDRESS = "\0kk-cap-search-v1"
MAX_REQ = 2048
MAX_RESP = 8192
ALLOWED_PEER_UID = 0
ALLOWED_PEER_UNIT = "kk-fk-tool-gateway.service"
FRESH_MARKERS = ("today","latest","current","news","breaking","reuters","ap ","今天","最新","当前","新闻","突发")
CACHE_TTL_SECONDS = 120.0
_CACHE: dict[str, tuple[float, list[dict]]] = {}


def peer_authorized(conn: socket.socket, proc_root: Path = Path("/proc")) -> bool:
    try:
        size = struct.calcsize("3i")
        pid, uid, _gid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size))
        if uid != ALLOWED_PEER_UID or pid <= 1:
            return False
        text = (proc_root / str(pid) / "cgroup").read_text(encoding="utf-8")
    except (OSError, ValueError, struct.error, UnicodeError):
        return False
    for line in text.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[2].rstrip("/").endswith("/" + ALLOWED_PEER_UNIT):
            return True
    return False

def strict(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_REQ:
        raise ValueError("size")
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("dup")
            out[key] = value
        return out
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=hook)
    if not isinstance(value, dict) or set(value) != {"schema", "query"}:
        raise ValueError("schema")
    if value.get("schema") != "KK.CAP.SEARCH.1":
        raise ValueError("schema")
    query = value.get("query")
    if not isinstance(query, str) or not (1 <= len(query) <= 200):
        raise ValueError("query")
    if any(ord(char) < 32 for char in query):
        raise ValueError("query")
    return value


def _weather_location(query: str) -> str | None:
    low = query.casefold()
    if "天气" not in query and "weather" not in low:
        return None
    location = query
    for token in ("今天","今日","现在","当前","实时","天气","怎么样","如何","请问","预报","气温","温度"):
        location = location.replace(token, " ")
    location = re.sub(r"(?i)\b(today|current|now|weather|forecast|temperature)\b", " ", location)
    location = location.replace("的", " ")
    location = re.sub(r"[，,。？?!！:：;；]+", " ", location)
    location = " ".join(location.split()).strip()
    return location[:80] if location else None


def _weather_search(query: str) -> list[dict] | None:
    location = _weather_location(query)
    if location is None:
        return None
    api = "https://wttr.in/" + urllib.parse.quote(location) + "?format=j1"
    request = urllib.request.Request(api, headers={"User-Agent": "KK-Capability-Search/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        value = json.loads(response.read(131072).decode("utf-8"))
    current = value["current_condition"][0]
    today = value["weather"][0]
    desc_items = current.get("weatherDesc") or []
    desc = desc_items[0].get("value", "") if desc_items and isinstance(desc_items[0], dict) else ""
    snippet = (
        f"气温 {current.get('temp_C','?')}°C，体感 {current.get('FeelsLikeC','?')}°C，"
        f"湿度 {current.get('humidity','?')}%，天气 {desc or '未知'}，"
        f"今日最高 {today.get('maxtempC','?')}°C，最低 {today.get('mintempC','?')}°C。"
    )
    page = "https://wttr.in/" + urllib.parse.quote(location)
    return [{"title": f"{location} 当前天气", "url": page, "snippet": snippet[:400]}]




def _clean_html_text(value: str) -> str:
    value = re.sub(r"<!--.*?-->", " ", value, flags=re.S)
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return " ".join(value.split()).strip()




def _decode_ddg_link(href: str) -> str:
    href = html.unescape(href).strip()
    if href.startswith("//"):
        href = "https:" + href
    try:
        parts = urllib.parse.urlsplit(href)
        if parts.netloc.endswith("duckduckgo.com") and parts.path.startswith("/l/"):
            values = urllib.parse.parse_qs(parts.query).get("uddg")
            if values:
                return values[0]
    except Exception:
        return ""
    return href


def _ddg_lite_search(query: str) -> list[dict]:
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read(250000).decode("utf-8", "ignore")
    results = []
    seen = set()
    pat = re.compile(
        r"<a[^>]+href=\"([^\"]+)\"[^>]*class=[\'\"]result-link[\'\"][^>]*>(.*?)</a>",
        re.S | re.I,
    )
    for match in pat.finditer(data):
        link = _decode_ddg_link(match.group(1))
        title = _clean_html_text(match.group(2))[:200]
        if not link.startswith(("http://", "https://")) or "duckduckgo.com" in urllib.parse.urlsplit(link).netloc:
            continue
        if not title or link in seen:
            continue
        after = data[match.end():match.end() + 3000]
        sm = re.search(
            r"<td class=[\'\"]result-snippet[\'\"]>(.*?)</td>",
            after,
            re.S | re.I,
        )
        snippet = _clean_html_text(sm.group(1))[:400] if sm else ""
        seen.add(link)
        results.append({"title": title, "url": link[:500], "snippet": snippet})
        if len(results) >= 3:
            break
    if not results:
        raise ValueError("no search results")
    return results



def _jina_ddg_search(query: str) -> list[dict]:
    target = "http://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    url = "https://r.jina.ai/" + target
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "KK-Capability-Search/1.0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(220000).decode("utf-8", "ignore")
    if "Markdown Content:" not in data:
        raise ValueError("jina search payload missing")
    body = data.split("Markdown Content:", 1)[1]
    results = []
    seen = set()
    pat = re.compile(
        r"(?m)^\d+\.\[(.+?)\]\((https?://[^)]+)\)\s*\n([^\n]*)"
    )
    for match in pat.finditer(body):
        title = match.group(1).strip()[:200]
        link = _decode_ddg_link(match.group(2))
        snippet = match.group(3).strip()[:400]
        if (
            not title
            or not link.startswith(("http://", "https://"))
            or link in seen
        ):
            continue
        seen.add(link)
        results.append({"title": title, "url": link[:500], "snippet": snippet})
        if len(results) >= 3:
            break
    if not results:
        raise ValueError("jina search returned no results")
    return results

def _brave_search(query: str) -> list[dict]:
    url = "https://search.brave.com/search?q=" + urllib.parse.quote(query)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        },
    )
    last_error = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = response.read(400000).decode("utf-8", "ignore")
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code != 429 or attempt:
                raise
            time.sleep(1.5)
    else:
        raise last_error if last_error is not None else ValueError("search unavailable")
    results = []
    seen = set()
    title_pat = re.compile(
        r'<div class="title search-snippet-title[^"]*" title="([^"]*)">',
        re.I,
    )
    for match in title_pat.finditer(data):
        title = _clean_html_text(match.group(1))[:200]
        before = data[max(0, match.start() - 6000):match.start()]
        hrefs = list(re.finditer(r'<a href="(https?://[^"]+)"[^>]*>', before, re.I))
        if not hrefs:
            continue
        link = html.unescape(hrefs[-1].group(1)).strip()
        if not link.startswith(("http://", "https://")) or "search.brave.com" in link:
            continue
        if link in seen:
            continue
        after = data[match.end():match.end() + 7000]
        snippet = ""
        sm = re.search(
            r'<div class="generic-snippet[^"]*">.*?<div class="content[^"]*">(.*?)</div>',
            after,
            re.S | re.I,
        )
        if sm:
            snippet = _clean_html_text(sm.group(1))[:400]
        if not title:
            continue
        seen.add(link)
        results.append({"title": title, "url": link[:500], "snippet": snippet})
        if len(results) >= 3:
            break
    if not results:
        raise ValueError("no relevant search results")
    return results

def search(query: str) -> list[dict]:
    now = time.monotonic()
    cached = _CACHE.get(query)
    if cached is not None and now - cached[0] <= CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    weather = _weather_search(query)
    if weather is not None:
        results = weather
    else:
        try:
            results = _ddg_lite_search(query)
        except Exception:
            try:
                results = _jina_ddg_search(query)
            except Exception:
                results = _brave_search(query)
    clean = [dict(item) for item in results[:3]]
    _CACHE[query] = (now, clean)
    if len(_CACHE) > 32:
        oldest = min(_CACHE, key=lambda key: _CACHE[key][0])
        _CACHE.pop(oldest, None)
    return [dict(item) for item in clean]


def _fail_receipt() -> bytes:
    return b'{"schema":"KK.CAP.SEARCH.RECEIPT.1","status":"FAIL","results":[]}\n'


def handle(conn: socket.socket) -> None:
    buf = bytearray()
    while b"\n" not in buf and len(buf) <= MAX_REQ:
        chunk = conn.recv(512)
        if not chunk:
            break
        buf.extend(chunk)
    try:
        if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
            raise ValueError("frame")
        value = strict(bytes(buf[:-1]))
        results = search(value["query"])
        out = {"schema": "KK.CAP.SEARCH.RECEIPT.1", "status": "PASS", "results": results}
        raw = (json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(raw) > MAX_RESP:
            raw = _fail_receipt()
    except Exception:
        raw = _fail_receipt()
    try:
        conn.sendall(raw)
    except (BrokenPipeError, ConnectionResetError, OSError):
        return

def main() -> None:
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(ADDRESS)
    server.listen(8)
    while True:
        conn, _ = server.accept()
        with conn:
            if not peer_authorized(conn):
                try:
                    conn.sendall(_fail_receipt())
                except OSError:
                    pass
                continue
            handle(conn)


if __name__ == "__main__":
    main()
