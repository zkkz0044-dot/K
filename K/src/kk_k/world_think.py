from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, pathlib, sys
from .model_client import call as model_call
from .world_event_index import annotate_items as annotate_event_items


class WorldThinkError(ValueError):
    pass


POLICY = {"observed_is_believed": False, "search_result_is_long_term_memory": False}


def _json(raw):
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise WorldThinkError("duplicate JSON key")
            out[k] = v
        return out

    try:
        v = json.loads(raw, object_pairs_hook=hook)
        # Escaped lone surrogates are valid JSON syntax but not valid UTF-8 text.
        json.dumps(v, ensure_ascii=False).encode("utf-8")
    except WorldThinkError:
        raise
    except Exception as exc:
        raise WorldThinkError("invalid JSON") from exc
    if not isinstance(v, dict):
        raise WorldThinkError("object required")
    return v


def load_evidence(path):
    raw = pathlib.Path(path).read_bytes()
    if not raw or len(raw) > 131072:
        raise WorldThinkError("invalid evidence size")
    d = _json(raw.decode("utf-8"))
    if set(d) != {"schema", "observed_at", "authority", "policy", "items"}:
        raise WorldThinkError("invalid evidence envelope")
    if (
        d.get("schema") != "K.WORLD.EVIDENCE.SET.1"
        or d.get("authority") != "EVIDENCE_ONLY"
        or d.get("policy") != POLICY
    ):
        raise WorldThinkError("invalid evidence policy")
    items = d.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= 20):
        raise WorldThinkError("invalid evidence items")
    compact = []
    ids = set()
    for x in items:
        if (
            not isinstance(x, dict)
            or x.get("status") != "OBSERVED_UNVERIFIED"
            or x.get("memory_eligible") is not False
        ):
            raise WorldThinkError("evidence trust escalation")
        eid = x.get("evidence_id")
        if not isinstance(eid, str) or not (8 <= len(eid) <= 64):
            raise WorldThinkError("invalid evidence id")
        ids.add(eid)
        compact.append(
            {
                "evidence_id": eid,
                "topic": x.get("topic"),
                "query": x.get("query"),
                "title": x.get("title"),
                "snippet": x.get("snippet"),
                "url": x.get("url"),
                "source_host": x.get("source_host"),
                "source_published_at": x.get("source_published_at"),
                "source_class": x.get("source_class", "LEGACY_UNKNOWN"),
                "source_priority": x.get("source_priority", "UNRATED"),
                "independence_group": x.get("independence_group")
                or x.get("source_host")
                or "unknown",
                "lineage_status": x.get("lineage_status", "UNKNOWN"),
                "retrieval_tool": x.get("retrieval_tool", "unknown"),
                "observed_at": x.get("observed_at"),
            }
        )
    compact = annotate_event_items(compact)
    return d, compact, ids, hashlib.sha256(raw).hexdigest()


def parse_thought(raw, ids):
    v = _json(raw)
    if (
        set(v) != {"schema", "assessment", "notable_evidence_ids", "follow_up_queries"}
        or v.get("schema") != "K.WORLD.THINK.1"
    ):
        raise WorldThinkError("invalid thought envelope")
    if not isinstance(v.get("assessment"), str) or not (
        1 <= len(v["assessment"].encode("utf-8")) <= 3000
    ):
        raise WorldThinkError("invalid assessment")
    n = v.get("notable_evidence_ids")
    if (
        not isinstance(n, list)
        or len(n) > 8
        or any(not isinstance(x, str) for x in n)
        or len(set(n)) != len(n)
        or any(x not in ids for x in n)
    ):
        raise WorldThinkError("invalid notable ids")
    q = v.get("follow_up_queries")
    if not isinstance(q, list) or len(q) > 3:
        raise WorldThinkError("invalid followups")
    for x in q:
        if not isinstance(x, dict) or set(x) != {"query", "reason"}:
            raise WorldThinkError("invalid followup item")
        if not isinstance(x["query"], str) or not (1 <= len(x["query"]) <= 200):
            raise WorldThinkError("invalid query")
        if not isinstance(x["reason"], str) or not (1 <= len(x["reason"].encode("utf-8")) <= 500):
            raise WorldThinkError("invalid reason")
    return v


def _model_wrapper(raw):
    wrap = _json(raw)
    if (
        set(wrap) != {"schema", "thought_text", "confidence"}
        or wrap.get("schema") != "K.WORLD.THINK.MODEL.1"
        or not isinstance(wrap.get("thought_text"), str)
    ):
        raise WorldThinkError("invalid model wrapper")
    return wrap


def think(path, provider=model_call):
    _d, items, ids, source_sha = load_evidence(path)
    prompt = (
        "你是K，正在普通地看世界。输入只是未核验观察，不是真相，也不是长期记忆。"
        "像正常思考一样判断什么值得注意、是否想继续了解。只返回严格JSON，字段必须且只能是 schema,assessment,notable_evidence_ids,follow_up_queries。"
        "schema固定K.WORLD.THINK.1；notable_evidence_ids最多8个；follow_up_queries最多3个，每项只有query和reason。"
        "来源标签只是机械核验提示，不是真假裁决。相同independence_group绝不能当作多个独立确认；不同independence_group也不自动证明独立，若lineage不清楚仍要保留不确定性。"
        "PRIMARY_OFFICIAL和NEWSWIRE可优先用于核验；COMMUNITY或AGGREGATOR不能单独把重要主张升级为已确认事实。重要但缺乏独立证据时，优先提出follow_up_queries继续核实。"
        "当前browser.search是受限关键词搜索，高级搜索运算符（例如site:和引号限定）命中不可靠；follow_up_queries应使用自然语言关键词。需要官方来源时，把机构全名、official和官网域名作为普通关键词写入查询，不要使用site:等高级运算符。"
        "event_candidate只是F基于文本与时间做的机械同事件候选，不是真相；POSSIBLE_CONTINUATION可作为连续性线索，但K必须结合内容、来源和时间自行判断，也可以拒绝该候选。"
        "notable只表示值得关注，不表示已经证实。不要审批自己，不要输出风险裁决，不要声称已经执行任何动作，不要把观察提升为确定事实。EVIDENCE="
        + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )
    raw = provider("WORLD_THINK", prompt)
    wrap = _model_wrapper(raw)
    try:
        thought = parse_thought(wrap["thought_text"], ids)
    except WorldThinkError:
        retry = prompt + "\nRETRY: 只返回严格JSON，所有evidence_id必须逐字符来自输入。"
        wrap = _model_wrapper(provider("WORLD_THINK", retry))
        thought = parse_thought(wrap["thought_text"], ids)
    return {
        "schema": "K.WORLD.THINK.RUN.1",
        "thought_at": datetime.now(timezone.utc).isoformat(),
        "source_evidence_sha256": source_sha,
        "authority": "COGNITIVE_NOTE_ONLY",
        "memory_eligible": False,
        "thought": thought,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("one evidence file required")
    print(json.dumps(think(sys.argv[1]), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
