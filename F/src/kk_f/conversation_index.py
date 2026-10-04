from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA = "FK_AUDIT.CONVERSATION_INDEX.1"
ZERO_DIGEST = "0" * 64
HUMAN_SUBJECTS = frozenset({"human_chat", "human_ask", "human_plan", "human_remember"})
_RECALL_ASCII = re.compile(r"[a-z0-9][a-z0-9._-]{1,63}")
_RECALL_CJK = re.compile(r"[\u4e00-\u9fff]+")
_RECALL_STOP = frozenset(
    {
        "the",
        "and",
        "with",
        "this",
        "that",
        "from",
        "about",
        "what",
        "how",
        "现在",
        "这个",
        "那个",
        "什么",
        "怎么",
        "一下",
        "我们",
        "你们",
        "他们",
        "可以",
        "还是",
    }
)


class ConversationIndexError(RuntimeError):
    pass


def recall_units(text: str) -> set[str]:
    lowered = text.casefold()
    units = {x for x in _RECALL_ASCII.findall(lowered) if x not in _RECALL_STOP}
    for segment in _RECALL_CJK.findall(text):
        if 2 <= len(segment) <= 12 and segment not in _RECALL_STOP:
            units.add(segment)
        for i in range(max(0, len(segment) - 1)):
            token = segment[i : i + 2]
            if token not in _RECALL_STOP:
                units.add(token)
    return units


def recall_compact(text: str) -> str:
    return "".join(ch.casefold() for ch in text if ch.isalnum())


def _canon(value: object) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise ConversationIndexError("INDEX_VALUE_INVALID") from exc


def _connect(path: str) -> sqlite3.Connection:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ConversationIndexError("INDEX_PATH_INVALID")
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
    CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1), schema TEXT NOT NULL, generation INTEGER NOT NULL, digest TEXT NOT NULL);
    CREATE TABLE pending(sequence INTEGER PRIMARY KEY, event_json TEXT NOT NULL);
    CREATE TABLE turns(reply_sequence INTEGER PRIMARY KEY, events_json TEXT NOT NULL, turn_sha256 TEXT NOT NULL, compact TEXT NOT NULL);
    CREATE TABLE terms(term TEXT NOT NULL, reply_sequence INTEGER NOT NULL, PRIMARY KEY(term,reply_sequence));
    CREATE INDEX terms_term_idx ON terms(term,reply_sequence);
    """
    )
    conn.execute(
        "INSERT INTO meta(id,schema,generation,digest) VALUES(1,?,?,?)", (SCHEMA, 0, ZERO_DIGEST)
    )


def _meta(conn: sqlite3.Connection) -> tuple[int, str]:
    row = conn.execute("SELECT schema,generation,digest FROM meta WHERE id=1").fetchone()
    if (
        row is None
        or row[0] != SCHEMA
        or type(row[1]) is not int
        or row[1] < 0
        or not isinstance(row[2], str)
        or len(row[2]) != 64
    ):
        raise ConversationIndexError("INDEX_META_INVALID")
    return row[1], row[2]


def _decode_events(raw: str, expected_sha: str) -> list[dict]:
    if not isinstance(raw, str) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != expected_sha:
        raise ConversationIndexError("INDEX_TURN_INVALID")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConversationIndexError("INDEX_TURN_INVALID") from exc
    if not isinstance(value, list) or not value or any(not isinstance(x, dict) for x in value):
        raise ConversationIndexError("INDEX_TURN_INVALID")
    return value


def _insert_turn(conn: sqlite3.Connection, turn: list[dict]) -> None:
    reply_seq = turn[-1].get("sequence")
    if type(reply_seq) is not int or reply_seq < 1 or turn[-1].get("subject") != "k_reply":
        raise ConversationIndexError("INDEX_TURN_INVALID")
    raw = _canon(turn)
    text = "\n".join(str(event.get("summary", "")) for event in turn)
    compact = recall_compact(text)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO turns(reply_sequence,events_json,turn_sha256,compact) VALUES(?,?,?,?)",
        (reply_seq, raw, digest, compact),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO terms(term,reply_sequence) VALUES(?,?)",
        ((term, reply_seq) for term in recall_units(text)),
    )


def _apply_event(conn: sqlite3.Connection, event: dict) -> None:
    subject = event.get("subject")
    if subject in HUMAN_SUBJECTS:
        seq = event.get("sequence")
        if type(seq) is not int or seq < 1:
            raise ConversationIndexError("INDEX_EVENT_INVALID")
        conn.execute("INSERT INTO pending(sequence,event_json) VALUES(?,?)", (seq, _canon(event)))
    elif subject == "dialogue_error":
        conn.execute("DELETE FROM pending")
    elif subject == "k_reply":
        rows = conn.execute("SELECT event_json FROM pending ORDER BY sequence").fetchall()
        if rows:
            pending = [json.loads(row[0]) for row in rows]
            _insert_turn(conn, pending + [event])
            conn.execute("DELETE FROM pending")


def rebuild_index(path: str, events: Iterable[dict]) -> tuple[int, str]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    conn = _connect(path)
    try:
        _schema(conn)
        generation, digest = 0, ZERO_DIGEST
        with conn:
            for event in events:
                _apply_event(conn, event)
                generation, digest = event["sequence"], event["entry_sha256"]
            conn.execute("UPDATE meta SET generation=?,digest=? WHERE id=1", (generation, digest))
        os.chmod(path, 0o600)
        return generation, digest
    except (sqlite3.DatabaseError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ConversationIndexError("INDEX_REBUILD_FAILED") from exc
    finally:
        conn.close()


def append_event(path: str, event: dict, generation: int, digest: str) -> None:
    conn = _connect(path)
    try:
        if conn.execute("PRAGMA quick_check(1)").fetchone() != ("ok",):
            raise ConversationIndexError("INDEX_CORRUPT")
        old_generation, old_digest = _meta(conn)
        if event.get("sequence") != old_generation + 1 or event.get("prev_sha256") != old_digest:
            raise ConversationIndexError("INDEX_HEAD_MISMATCH")
        if generation != event.get("sequence") or digest != event.get("entry_sha256"):
            raise ConversationIndexError("INDEX_COMMIT_MISMATCH")
        with conn:
            _apply_event(conn, event)
            conn.execute("UPDATE meta SET generation=?,digest=? WHERE id=1", (generation, digest))
    except sqlite3.DatabaseError as exc:
        raise ConversationIndexError("INDEX_UPDATE_FAILED") from exc
    finally:
        conn.close()


def matches_state(path: str, generation: int, digest: str) -> bool:
    try:
        conn = _connect(path)
        try:
            if conn.execute("PRAGMA quick_check(1)").fetchone() != ("ok",):
                return False
            return _meta(conn) == (generation, digest)
        finally:
            conn.close()
    except (ConversationIndexError, sqlite3.DatabaseError, OSError):
        return False


def recent_events(path: str, limit: int) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ConversationIndexError("INDEX_LIMIT_INVALID")
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT events_json,turn_sha256 FROM turns ORDER BY reply_sequence DESC LIMIT ?",
            (limit,),
        ).fetchall()
        events = []
        for raw, digest in reversed(rows):
            events.extend(_decode_events(raw, digest))
        return events[-limit:]
    except sqlite3.DatabaseError as exc:
        raise ConversationIndexError("INDEX_QUERY_FAILED") from exc
    finally:
        conn.close()


def recall_events(path: str, query: str, limit: int) -> list[dict]:
    if (
        not isinstance(query, str)
        or not query.strip()
        or type(limit) is not int
        or not 1 <= limit <= 4
    ):
        raise ConversationIndexError("INDEX_QUERY_INVALID")
    q_units = recall_units(query)
    q_compact = recall_compact(query)
    if not q_units and len(q_compact) < 2:
        return []
    cap = max(32, limit * 8)
    conn = _connect(path)
    try:
        candidates = set()
        if q_units:
            units = sorted(q_units)
            marks = ",".join("?" for _ in units)
            sql = f"SELECT reply_sequence,COUNT(*) c FROM terms WHERE term IN ({marks}) GROUP BY reply_sequence ORDER BY c DESC,reply_sequence DESC LIMIT ?"
            candidates.update(row[0] for row in conn.execute(sql, (*units, cap * 2)))
        if len(q_compact) >= 4:
            candidates.update(
                row[0]
                for row in conn.execute(
                    "SELECT reply_sequence FROM turns WHERE instr(compact,?)>0 ORDER BY reply_sequence DESC LIMIT ?",
                    (q_compact, cap),
                )
            )
        if not candidates:
            return []
        marks = ",".join("?" for _ in candidates)
        rows = conn.execute(
            f"SELECT reply_sequence,events_json,turn_sha256 FROM turns WHERE reply_sequence IN ({marks})",
            tuple(candidates),
        ).fetchall()
        ranked = []
        for seq, raw, digest in rows:
            turn = _decode_events(raw, digest)
            text = "\n".join(str(event.get("summary", "")) for event in turn)
            units = recall_units(text)
            compact = recall_compact(text)
            overlap = len(q_units & units)
            phrase = bool(q_compact and len(q_compact) >= 4 and q_compact in compact)
            if overlap == 0 and not phrase:
                continue
            ranked.append((overlap * 10 + (80 if phrase else 0), seq, turn))
        ranked.sort(key=lambda item: (-item[0], -item[1]))
        selected = []
        budget = 11000
        turns_used = 0
        for _score, _seq, turn in ranked:
            if turns_used >= limit:
                break
            encoded = _canon(turn).encode("utf-8")
            if len(encoded) > budget:
                continue
            selected.extend(turn)
            budget -= len(encoded)
            turns_used += 1
        selected.sort(key=lambda event: event.get("sequence", 0))
        return selected
    except sqlite3.DatabaseError as exc:
        raise ConversationIndexError("INDEX_QUERY_FAILED") from exc
    finally:
        conn.close()
