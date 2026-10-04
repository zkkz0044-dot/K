from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, os, pathlib, re, unicodedata

STATE_SCHEMA = "K.WORLD.EVENT.STATE.1"
UPDATE_SCHEMA = "K.WORLD.EVENT.UPDATE.1"
AUTHORITY = "DERIVED_EVENT_CANDIDATE_ONLY"
MAX_ACTIVE = 64
MAX_AGE_DAYS = 45
MATCH_THRESHOLD = 0.52
STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "after",
    "before",
    "into",
    "over",
    "under",
    "says",
    "say",
    "said",
    "report",
    "reports",
    "new",
    "latest",
    "amid",
    "about",
    "have",
    "has",
    "had",
    "will",
    "would",
    "could",
    "should",
    "its",
    "their",
    "they",
    "them",
    "are",
    "was",
    "were",
    "been",
    "being",
    "not",
    "but",
    "more",
    "most",
    "some",
    "than",
    "then",
    "when",
    "where",
    "what",
    "who",
    "why",
    "how",
}


class EventIndexError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _canon(obj):
    return (
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _atomic(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canon(obj)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_bytes(raw)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return hashlib.sha256(raw).hexdigest()


def _norm(s):
    return unicodedata.normalize("NFKC", str(s or "")).lower().strip()


def text_tokens(title, snippet=""):
    text = _norm(f"{title} {snippet}")
    toks = set()
    for w in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text):
        if w not in STOP:
            toks.add(w)
    for seg in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for i in range(len(seg) - 1):
            toks.add(seg[i : i + 2])
    return sorted(toks)[:256]


def stable_fingerprint(item):
    core = {
        "topic": _norm(item.get("topic")),
        "url": _norm(item.get("url")),
        "title": _norm(item.get("title")),
        "snippet": _norm(item.get("snippet")),
    }
    return hashlib.sha256(
        json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _jaccard(a, b):
    a = set(a or ())
    b = set(b or ())
    if not a or not b:
        return 0.0, 0
    inter = len(a & b)
    return inter / len(a | b), inter


def _parse_time(v):
    try:
        d = datetime.fromisoformat(str(v))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _fresh(event, now):
    dt = _parse_time(event.get("last_seen"))
    return bool(dt and (now - dt.astimezone(timezone.utc)).total_seconds() <= MAX_AGE_DAYS * 86400)


def _probe_is_file(path):
    try:
        return path.is_file()
    except OSError:
        return False


def _empty_state():
    return {
        "schema": STATE_SCHEMA,
        "updated_at": None,
        "authority": AUTHORITY,
        "truth_status": "UNVERIFIED",
        "memory_eligible": False,
        "events": [],
    }


def load_state(path=None):
    if path is None:
        candidates = [
            pathlib.Path("/run/kk-k-ro/world/event_state/current.json"),
            pathlib.Path("/root/K/K/world/event_state/current.json"),
        ]
        path = next((p for p in candidates if _probe_is_file(p)), None)
        if path is None:
            return _empty_state()
    else:
        path = pathlib.Path(path)
        if not path.is_file():
            return _empty_state()
    raw = path.read_bytes()
    if not raw or len(raw) > 524288:
        raise EventIndexError("invalid event state size")
    d = json.loads(raw)
    if not isinstance(d, dict) or set(d) != {
        "schema",
        "updated_at",
        "authority",
        "truth_status",
        "memory_eligible",
        "events",
    }:
        raise EventIndexError("invalid event state envelope")
    if (
        d.get("schema") != STATE_SCHEMA
        or d.get("authority") != AUTHORITY
        or d.get("truth_status") != "UNVERIFIED"
        or d.get("memory_eligible") is not False
    ):
        raise EventIndexError("invalid event state policy")
    if not isinstance(d.get("events"), list) or len(d["events"]) > MAX_ACTIVE:
        raise EventIndexError("invalid event list")
    return d


def match_event(item, events, now=None):
    now = now or _now()
    topic = _norm(item.get("topic"))
    url = _norm(item.get("url"))
    toks = text_tokens(item.get("title"), item.get("snippet"))
    fp = stable_fingerprint(item)
    best = None
    best_score = 0.0
    for ev in events:
        if not isinstance(ev, dict) or _norm(ev.get("topic")) != topic or not _fresh(ev, now):
            continue
        if fp in ev.get("evidence_fingerprints", []):
            return ev, 1.0, "EXACT_CONTENT"
        if url and url in ev.get("recent_urls", []):
            return ev, 1.0, "SAME_URL"
        s1, i1 = _jaccard(toks, ev.get("anchor_tokens", []))
        s2, i2 = _jaccard(toks, ev.get("last_tokens", []))
        score = max(s1, s2)
        shared = max(i1, i2)
        if shared >= 3 and score >= MATCH_THRESHOLD and score > best_score:
            best = ev
            best_score = score
    return (best, best_score, "TOKEN_SIMILARITY") if best else (None, 0.0, "NO_STRONG_MATCH")


def annotate_items(items, state_path=None, now=None):
    state = load_state(state_path)
    events = state["events"]
    now = now or _now()
    out = []
    for item in items:
        ev, score, reason = match_event(item, events, now)
        x = dict(item)
        x["event_candidate"] = {
            "event_id": ev.get("event_id") if ev else None,
            "subject": ev.get("subject") if ev else None,
            "latest_subject": ev.get("latest_subject") if ev else None,
            "first_seen": ev.get("first_seen") if ev else None,
            "last_seen": ev.get("last_seen") if ev else None,
            "update_count": int(ev.get("update_count", 0)) if ev else 0,
            "source_groups": list(ev.get("source_groups", []))[:8] if ev else [],
            "relation": "POSSIBLE_CONTINUATION" if ev else "NO_STRONG_MATCH",
            "mechanical_similarity": round(score, 3),
            "match_reason": reason,
            "truth_status": "UNVERIFIED",
        }
        out.append(x)
    return out


def _event_id(item, fp):
    return "evt-" + hashlib.sha256((_norm(item.get("topic")) + "|" + fp).encode()).hexdigest()[:16]


def _bounded_union(old, new, limit):
    out = []
    for v in list(old or []) + list(new or []):
        if v and v not in out:
            out.append(v)
    return out[-limit:]


def apply_notable(items, state_dir, updates_dir, now=None):
    now = now or _now()
    state_dir = pathlib.Path(state_dir)
    updates_dir = pathlib.Path(updates_dir)
    state_path = state_dir / "current.json"
    state = load_state(state_path)
    events = state["events"]
    update_paths = []
    skipped = 0
    for item in items:
        fp = stable_fingerprint(item)
        if any(fp in ev.get("evidence_fingerprints", []) for ev in events):
            skipped += 1
            continue
        ev, score, reason = match_event(item, events, now)
        relation = "CONTINUING_CANDIDATE" if ev else "NEW_CANDIDATE"
        toks = text_tokens(item.get("title"), item.get("snippet"))
        observed = str(item.get("observed_at") or now.isoformat())
        url = _norm(item.get("url"))
        group = str(item.get("independence_group") or item.get("source_host") or "unknown")
        sclass = str(item.get("source_class") or "LEGACY_UNKNOWN")
        if ev is None:
            ev = {
                "event_id": _event_id(item, fp),
                "topic": str(item.get("topic") or "unknown"),
                "subject": str(item.get("title") or "untitled")[:500],
                "latest_subject": str(item.get("title") or "untitled")[:500],
                "first_seen": observed,
                "last_seen": observed,
                "update_count": 1,
                "anchor_tokens": toks,
                "last_tokens": toks,
                "source_groups": [group],
                "source_classes": [sclass],
                "evidence_fingerprints": [fp],
                "recent_urls": [url] if url else [],
            }
            events.append(ev)
        else:
            ev["latest_subject"] = str(
                item.get("title") or ev.get("latest_subject") or ev.get("subject")
            )[:500]
            ev["last_seen"] = observed
            ev["update_count"] = int(ev.get("update_count", 0)) + 1
            ev["last_tokens"] = toks
            ev["source_groups"] = _bounded_union(ev.get("source_groups"), [group], 16)
            ev["source_classes"] = _bounded_union(ev.get("source_classes"), [sclass], 8)
            ev["evidence_fingerprints"] = _bounded_union(ev.get("evidence_fingerprints"), [fp], 64)
            ev["recent_urls"] = _bounded_union(ev.get("recent_urls"), [url] if url else [], 16)
        upd = {
            "schema": UPDATE_SCHEMA,
            "updated_at": now.isoformat(),
            "event_id": ev["event_id"],
            "relation": relation,
            "topic": ev["topic"],
            "subject": ev["subject"],
            "latest_subject": ev["latest_subject"],
            "observed_at": observed,
            "evidence_id": item.get("evidence_id"),
            "evidence_fingerprint": fp,
            "source_group": group,
            "source_class": sclass,
            "mechanical_similarity": round(score, 3),
            "match_reason": reason,
            "authority": AUTHORITY,
            "truth_status": "UNVERIFIED",
            "memory_eligible": False,
        }
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        target = updates_dir / f'{stamp}-{ev["event_id"]}-{fp[:10]}.json'
        _atomic(target, upd)
        update_paths.append(str(target))
    events.sort(key=lambda e: str(e.get("last_seen") or ""), reverse=True)
    events[:] = events[:MAX_ACTIVE]
    state = {
        "schema": STATE_SCHEMA,
        "updated_at": now.isoformat(),
        "authority": AUTHORITY,
        "truth_status": "UNVERIFIED",
        "memory_eligible": False,
        "events": events,
    }
    _atomic(state_path, state)
    return {
        "updates": update_paths,
        "state": str(state_path),
        "active_events": len(events),
        "skipped": skipped,
    }
