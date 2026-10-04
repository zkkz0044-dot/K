from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, math, pathlib, sys
from .external_tools import execute_external_tool


class FollowupThinkError(ValueError):
    pass


def _strict_json(raw):
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise FollowupThinkError("duplicate JSON key")
            out[key] = value
        return out

    def constant(_value):
        raise FollowupThinkError("nonfinite JSON value")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise FollowupThinkError("nonfinite JSON value")
        return number

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=hook,
            parse_constant=constant,
            parse_float=finite_float,
        )
    except FollowupThinkError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise FollowupThinkError("invalid thought JSON") from exc


def _query_item(item):
    if not isinstance(item, dict) or set(item) != {"query", "reason"}:
        raise FollowupThinkError("invalid followup item")
    query, reason = item["query"], item["reason"]
    if not isinstance(query, str) or not 1 <= len(query) <= 200 or not query.strip():
        raise FollowupThinkError("invalid query")
    if any(ord(char) < 32 for char in query):
        raise FollowupThinkError("invalid query")
    if not isinstance(reason, str) or not reason.strip():
        raise FollowupThinkError("invalid reason")
    try:
        query.encode("utf-8")
        size = len(reason.encode("utf-8"))
    except UnicodeError as exc:
        raise FollowupThinkError("invalid query text encoding") from exc
    if not 1 <= size <= 500:
        raise FollowupThinkError("invalid reason")
    return {"query": query, "reason": reason}


def load_queries(path):
    raw = pathlib.Path(path).read_bytes()
    if not raw or len(raw) > 65536:
        raise FollowupThinkError("invalid thought size")
    d = _strict_json(raw)
    need = {
        "schema",
        "thought_at",
        "source_evidence_sha256",
        "authority",
        "memory_eligible",
        "thought",
    }
    if not isinstance(d, dict) or set(d) != need or d.get("schema") != "K.WORLD.THINK.RUN.1":
        raise FollowupThinkError("invalid thought envelope")
    if d.get("authority") != "COGNITIVE_NOTE_ONLY" or d.get("memory_eligible") is not False:
        raise FollowupThinkError("invalid thought policy")
    t = d.get("thought")
    if (
        not isinstance(t, dict)
        or set(t) != {"schema", "assessment", "notable_evidence_ids", "follow_up_queries"}
        or t.get("schema") != "K.WORLD.THINK.1"
    ):
        raise FollowupThinkError("invalid thought")
    q = t.get("follow_up_queries")
    if not isinstance(q, list) or len(q) > 3:
        raise FollowupThinkError("invalid followups")
    # Validate the entire batch before allowing even its first external request.
    checked = [_query_item(item) for item in q]
    unique = []
    seen = set()
    for item in checked:
        key = item["query"]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    # Retain the existing raw-file digest convention for lineage compatibility.
    return unique, hashlib.sha256(raw).hexdigest()


def observe(path, executor=execute_external_tool):
    queries, parent_sha = load_queries(path)
    items = []
    for x in queries:
        if not isinstance(x, dict) or set(x) != {"query", "reason"}:
            raise FollowupThinkError("invalid followup item")
        try:
            r = executor(
                {
                    "schema": "K.EXTERNAL.TOOL.REQUEST.2",
                    "tool": "browser.search",
                    "args": {"query": x["query"]},
                }
            )
            items.append(
                {"query": x["query"], "reason": x["reason"], "verdict": r["verdict"], "receipt": r}
            )
        except Exception:
            items.append(
                {"query": x["query"], "reason": x["reason"], "verdict": "VETO", "receipt": None}
            )
    return {
        "schema": "K.WORLD.FOLLOWUP.BATCH.1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "parent_judgment_sha256": parent_sha,
        "authority": "EVIDENCE_ONLY",
        "items": items,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("one thought file required")
    print(
        json.dumps(observe(sys.argv[1]), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


if __name__ == "__main__":
    main()
