from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, pathlib, sys
from .external_tools import execute_external_tool

TOP = frozenset(
    {
        "schema",
        "judged_at",
        "source_observed_at",
        "source_evidence_sha256",
        "authority",
        "memory_eligible",
        "status",
        "proposal",
        "critic",
        "judge",
    }
)
PKEYS = frozenset(
    {
        "schema",
        "assessment",
        "priority_evidence_ids",
        "noise_evidence_ids",
        "corroborate_evidence_ids",
        "follow_up_queries",
    }
)


class FollowupError(ValueError):
    pass


def _json(raw: bytes) -> dict:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise FollowupError("duplicate JSON key")
            out[k] = v
        return out

    try:
        d = json.loads(raw.decode("utf-8"), object_pairs_hook=hook)
    except FollowupError:
        raise
    except Exception as exc:
        raise FollowupError("invalid JSON") from exc
    if not isinstance(d, dict):
        raise FollowupError("object required")
    return d


def load_queries(path: str) -> tuple[list[dict], str]:
    raw = pathlib.Path(path).read_bytes()
    if not raw or len(raw) > 65536:
        raise FollowupError("invalid judgment size")
    d = _json(raw)
    if frozenset(d) != TOP or d.get("schema") != "K.WORLD.JUDGMENT.RUN.1":
        raise FollowupError("invalid judgment envelope")
    if d.get("authority") != "COGNITIVE_PROPOSAL_ONLY" or d.get("memory_eligible") is not False:
        raise FollowupError("judgment not eligible")
    if d.get("status") not in {"APPROVED_PROVISIONAL", "REJECTED"}:
        raise FollowupError("invalid judgment status")
    if d.get("status") == "REJECTED":
        return [], hashlib.sha256(raw).hexdigest()
    p = d.get("proposal")
    if (
        not isinstance(p, dict)
        or frozenset(p) != PKEYS
        or p.get("schema") != "K.WORLD.JUDGMENT.PROPOSAL.1"
    ):
        raise FollowupError("invalid proposal")
    q = p.get("follow_up_queries")
    if not isinstance(q, list) or len(q) > 3:
        raise FollowupError("invalid followups")
    for x in q:
        if not isinstance(x, dict) or set(x) != {"query", "reason"}:
            raise FollowupError("invalid followup item")
        if not isinstance(x["query"], str) or not (1 <= len(x["query"]) <= 200):
            raise FollowupError("invalid query")
        if not isinstance(x["reason"], str) or not (1 <= len(x["reason"].encode("utf-8")) <= 500):
            raise FollowupError("invalid reason")
    return q, hashlib.sha256(raw).hexdigest()


def observe_followups(path: str, executor=execute_external_tool) -> dict:
    queries, parent_sha = load_queries(path)
    items = []
    for x in queries:
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


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("one judgment file required")
    print(
        json.dumps(
            observe_followups(sys.argv[1]),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
