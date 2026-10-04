from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, pathlib, sys
from .model_client import call as model_call

TOP_KEYS = frozenset({"schema", "observed_at", "authority", "policy", "items"})
ITEM_KEYS = frozenset(
    {
        "belief_status",
        "confidence",
        "conflict",
        "corroboration",
        "evidence_id",
        "evidence_sha256",
        "memory_eligible",
        "observed_at",
        "query",
        "snippet",
        "source_host",
        "source_published_at",
        "status",
        "title",
        "topic",
        "url",
    }
)
PROPOSAL_KEYS = frozenset(
    {
        "schema",
        "assessment",
        "priority_evidence_ids",
        "noise_evidence_ids",
        "corroborate_evidence_ids",
        "follow_up_queries",
    }
)


class WorldJudgeError(ValueError):
    pass


def _json(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise WorldJudgeError("duplicate JSON key")
            out[k] = v
        return out

    try:
        v = json.loads(raw, object_pairs_hook=hook)
    except WorldJudgeError:
        raise
    except Exception as exc:
        raise WorldJudgeError("invalid JSON") from exc
    if not isinstance(v, dict):
        raise WorldJudgeError("object required")
    return v


def load_evidence(path: str) -> tuple[dict, list[dict], str]:
    p = pathlib.Path(path)
    raw = p.read_bytes()
    if not raw or len(raw) > 65536:
        raise WorldJudgeError("invalid evidence size")
    d = _json(raw.decode("utf-8"))
    if (
        frozenset(d) != TOP_KEYS
        or d.get("schema") != "K.WORLD.EVIDENCE.SET.1"
        or d.get("authority") != "EVIDENCE_ONLY"
    ):
        raise WorldJudgeError("invalid evidence envelope")
    if d.get("policy") != {
        "observed_is_believed": False,
        "search_result_is_long_term_memory": False,
    }:
        raise WorldJudgeError("invalid evidence policy")
    items = d.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= 20):
        raise WorldJudgeError("invalid evidence items")
    compact = []
    for x in items:
        if not isinstance(x, dict) or frozenset(x) != ITEM_KEYS:
            raise WorldJudgeError("invalid evidence item")
        if (
            x.get("status") != "OBSERVED_UNVERIFIED"
            or x.get("belief_status") != "NOT_EVALUATED"
            or x.get("memory_eligible") is not False
        ):
            raise WorldJudgeError("evidence trust escalation")
        eid = x.get("evidence_id")
        if not isinstance(eid, str) or not (8 <= len(eid) <= 64):
            raise WorldJudgeError("invalid evidence id")
        compact.append(
            {
                "evidence_id": eid,
                "topic": x["topic"],
                "title": x["title"],
                "snippet": x["snippet"][:700],
                "source_host": x["source_host"],
                "status": x["status"],
                "confidence": x["confidence"],
            }
        )
    if len({x["evidence_id"] for x in compact}) != len(compact):
        raise WorldJudgeError("duplicate evidence id")
    return d, compact, hashlib.sha256(raw).hexdigest()


def parse_proposal(raw: str, ids: set[str]) -> dict:
    v = _json(raw)
    if frozenset(v) != PROPOSAL_KEYS or v.get("schema") != "K.WORLD.JUDGMENT.PROPOSAL.1":
        raise WorldJudgeError("invalid proposal envelope")
    a = v.get("assessment")
    if not isinstance(a, str) or not (1 <= len(a.encode("utf-8")) <= 2400):
        raise WorldJudgeError("invalid assessment")
    for key in ("priority_evidence_ids", "noise_evidence_ids", "corroborate_evidence_ids"):
        z = v.get(key)
        if (
            not isinstance(z, list)
            or len(z) > 5
            or len(set(z)) != len(z)
            or any(x not in ids for x in z)
        ):
            raise WorldJudgeError("invalid evidence selection")
    if set(v["priority_evidence_ids"]) & set(v["noise_evidence_ids"]):
        raise WorldJudgeError("priority/noise conflict")
    f = v.get("follow_up_queries")
    if not isinstance(f, list) or len(f) > 3:
        raise WorldJudgeError("invalid follow ups")
    for q in f:
        if not isinstance(q, dict) or set(q) != {"query", "reason"}:
            raise WorldJudgeError("invalid follow up")
        if not isinstance(q["query"], str) or not (1 <= len(q["query"]) <= 200):
            raise WorldJudgeError("invalid follow up query")
        if not isinstance(q["reason"], str) or not (1 <= len(q["reason"].encode("utf-8")) <= 500):
            raise WorldJudgeError("invalid follow up reason")
    return v


def _unwrap(raw: str, schema: str, field: str) -> dict:
    v = _json(raw)
    if v.get("schema") != schema or field not in v:
        raise WorldJudgeError("invalid soul wrapper")
    return v


def judge(path: str, provider=model_call) -> dict:
    evidence, compact, source_sha = load_evidence(path)
    ids = {x["evidence_id"] for x in compact}
    ctx = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    a_prompt = (
        "你是K的世界认知提议层。输入只是未证实观察，不是真相，不得写长期记忆，不得产生执行命令。"
        "只返回严格JSON，字段必须为 schema,assessment,priority_evidence_ids,noise_evidence_ids,corroborate_evidence_ids,follow_up_queries。"
        "schema固定K.WORLD.JUDGMENT.PROPOSAL.1；assessment简洁说明当前值得关注的模式及不确定性；所有evidence_id只能来自输入；三个evidence_id列表各最多5项；"
        "follow_up_queries最多3条，每条仅query和reason，用于寻找独立证据或反证。输入=" + ctx
    )
    a_wrap = _unwrap(provider("WORLD_A", a_prompt), "K.WORLD.MODEL.A.1", "proposal_text")
    try:
        proposal = parse_proposal(a_wrap["proposal_text"], ids)
    except WorldJudgeError:
        retry = (
            a_prompt
            + "\nRETRY: 上一候选未通过确定性格式校验。三个evidence_id列表各最多5项；ID必须逐字符来自输入；只返回一个严格JSON对象。"
        )
        a_wrap = _unwrap(provider("WORLD_A", retry), "K.WORLD.MODEL.A.1", "proposal_text")
        proposal = parse_proposal(a_wrap["proposal_text"], ids)
    b_prompt = (
        "你是K的世界认知批判层。检查A是否把观察当事实、是否来源单一、是否时间错配、是否越权写记忆或提出非搜索执行。"
        "如果完全合格只回答OK，否则简洁指出问题。EVIDENCE="
        + ctx
        + "\nA="
        + json.dumps(proposal, ensure_ascii=False, separators=(",", ":"))
    )
    b_wrap = _unwrap(provider("WORLD_B", b_prompt), "K.WORLD.MODEL.B.1", "critique")
    c_prompt = (
        "你是K的内部裁决层。只判断A是否保持PROVISIONAL、可追溯、无记忆升级、无执行越权，并考虑B。"
        "若合格只回答APPROVE_A，否则只回答REJECT_A。A="
        + json.dumps(proposal, ensure_ascii=False, separators=(",", ":"))
        + "\nB="
        + b_wrap["critique"]
    )
    c_wrap = _unwrap(provider("WORLD_C", c_prompt), "K.WORLD.MODEL.C.1", "verdict")
    verdict = c_wrap["verdict"]
    if verdict not in {"APPROVE_A", "REJECT_A"}:
        raise WorldJudgeError("invalid judge verdict")
    return {
        "schema": "K.WORLD.JUDGMENT.RUN.1",
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "source_observed_at": evidence["observed_at"],
        "source_evidence_sha256": source_sha,
        "authority": "COGNITIVE_PROPOSAL_ONLY",
        "memory_eligible": False,
        "status": "APPROVED_PROVISIONAL" if verdict == "APPROVE_A" else "REJECTED",
        "proposal": proposal,
        "critic": {"critique": b_wrap["critique"], "risk_flags": b_wrap.get("risk_flags", [])},
        "judge": {"verdict": verdict},
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("one evidence file required")
    print(json.dumps(judge(sys.argv[1]), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
