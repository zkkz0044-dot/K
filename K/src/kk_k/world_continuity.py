from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, pathlib, sys
from .model_client import call as model_call

STATUSES = frozenset({"NEW", "PERSISTING", "CHANGED", "CONTRADICTED", "STALE"})
CONF = frozenset({"LOW"})


class ContinuityError(ValueError):
    pass


def _json(raw):
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ContinuityError("duplicate JSON key")
            out[k] = v
        return out

    try:
        v = json.loads(raw, object_pairs_hook=hook)
    except ContinuityError:
        raise
    except Exception as exc:
        raise ContinuityError("invalid JSON") from exc
    if not isinstance(v, dict):
        raise ContinuityError("object required")
    return v


def load_context(path):
    raw = pathlib.Path(path).read_bytes()
    if not raw or len(raw) > 131072:
        raise ContinuityError("invalid context size")
    d = _json(raw.decode("utf-8"))
    if set(d) != {"schema", "generated_at", "authority", "memory_eligible", "rounds"}:
        raise ContinuityError("invalid context envelope")
    if (
        d.get("schema") != "K.WORLD.CONTINUITY.CONTEXT.1"
        or d.get("authority") != "EVIDENCE_ONLY"
        or d.get("memory_eligible") is not False
    ):
        raise ContinuityError("invalid context policy")
    rounds = d.get("rounds")
    if not isinstance(rounds, list) or not (2 <= len(rounds) <= 4):
        raise ContinuityError("invalid rounds")
    ids = set()
    rsha = set()
    compact = []
    for r in rounds:
        need = {
            "observed_at",
            "round_context_sha256",
            "evidence",
            "judged_at",
            "judgment_sha256",
            "judgment_status",
            "assessment",
            "priority_evidence_ids",
            "corroborate_evidence_ids",
        }
        if not isinstance(r, dict) or set(r) != need:
            raise ContinuityError("invalid round")
        if r.get("judgment_status") not in {"APPROVED_PROVISIONAL", "REJECTED"}:
            raise ContinuityError("invalid round judgment")
        rh = r.get("round_context_sha256")
        jh = r.get("judgment_sha256")
        if not isinstance(rh, str) or len(rh) != 64 or not isinstance(jh, str) or len(jh) != 64:
            raise ContinuityError("invalid hashes")
        rsha.add(rh)
        ev = []
        if not isinstance(r.get("evidence"), list) or len(r["evidence"]) > 12:
            raise ContinuityError("invalid round evidence")
        for x in r["evidence"]:
            if not isinstance(x, dict) or set(x) != {
                "evidence_id",
                "topic",
                "title",
                "source_host",
                "observed_at",
            }:
                raise ContinuityError("invalid compact evidence")
            eid = x.get("evidence_id")
            if not isinstance(eid, str) or not (8 <= len(eid) <= 64):
                raise ContinuityError("invalid evidence id")
            ids.add(eid)
            ev.append(x)
        compact.append(
            {
                "observed_at": r["observed_at"],
                "round_context_sha256": rh,
                "evidence": ev,
                "judged_at": r["judged_at"],
                "judgment_sha256": jh,
                "judgment_status": r["judgment_status"],
                "assessment": r["assessment"],
                "priority_evidence_ids": r["priority_evidence_ids"],
                "corroborate_evidence_ids": r["corroborate_evidence_ids"],
            }
        )
    return d, compact, ids, rsha, hashlib.sha256(raw).hexdigest()


def parse_proposal(raw, ids, rsha, current=None):
    v = _json(raw)
    if (
        set(v) != {"schema", "assessment", "items"}
        or v.get("schema") != "K.WORLD.CONTINUITY.PROPOSAL.1"
    ):
        raise ContinuityError("invalid proposal envelope")
    if not isinstance(v.get("assessment"), str) or not (
        1 <= len(v["assessment"].encode("utf-8")) <= 800
    ):
        raise ContinuityError("invalid assessment")
    items = v.get("items")
    if not isinstance(items, list) or len(items) > 4:
        raise ContinuityError("invalid continuity items")
    for x in items:
        need = {
            "subject",
            "status",
            "evidence_ids",
            "round_context_sha256s",
            "rationale",
            "confidence",
        }
        if not isinstance(x, dict) or set(x) != need:
            raise ContinuityError("invalid continuity item")
        if not isinstance(x["subject"], str) or not (1 <= len(x["subject"].encode("utf-8")) <= 240):
            raise ContinuityError("invalid subject")
        if x["status"] not in STATUSES or x["confidence"] not in CONF:
            raise ContinuityError("invalid status/confidence")
        e = x["evidence_ids"]
        rs = x["round_context_sha256s"]
        if (
            not isinstance(e, list)
            or not (1 <= len(e) <= 6)
            or len(set(e)) != len(e)
            or any(z not in ids for z in e)
        ):
            raise ContinuityError("invalid evidence refs")
        if (
            not isinstance(rs, list)
            or not (1 <= len(rs) <= 4)
            or len(set(rs)) != len(rs)
            or any(z not in rsha for z in rs)
        ):
            raise ContinuityError("invalid round refs")
        status = x["status"]
        if current is None:
            if status in {"PERSISTING", "CHANGED", "CONTRADICTED"} and len(rs) < 2:
                raise ContinuityError("cross-round status needs two rounds")
        else:
            if status == "NEW" and set(rs) != {current}:
                raise ContinuityError("NEW must reference current only")
            if status == "STALE" and current in rs:
                raise ContinuityError("STALE cannot reference current")
            if status in {"PERSISTING", "CHANGED", "CONTRADICTED"} and (
                current not in rs or len(rs) < 2
            ):
                raise ContinuityError("cross-round status needs current and history")
        if not isinstance(x["rationale"], str) or not (
            1 <= len(x["rationale"].encode("utf-8")) <= 300
        ):
            raise ContinuityError("invalid rationale")
    return v


def _unwrap(raw, schema, field):
    v = _json(raw)
    if v.get("schema") != schema or field not in v:
        raise ContinuityError("invalid model wrapper")
    return v


def evaluate(path, provider=model_call):
    _ctx, rounds, ids, rsha, source_sha = load_context(path)
    current = rounds[-1]["round_context_sha256"]
    context = json.dumps(rounds, ensure_ascii=False, separators=(",", ":"))
    a_prompt = (
        "你是K的跨轮世界连续性提议层。输入全部是未证实观察和临时判断，不是真相，也不是长期记忆。"
        "只返回一个严格JSON对象，字段必须且只能是 schema,assessment,items。schema固定K.WORLD.CONTINUITY.PROPOSAL.1。"
        "items最多4项；每项字段必须且只能是 subject,status,evidence_ids,round_context_sha256s,rationale,confidence。"
        "status只能是NEW,PERSISTING,CHANGED,CONTRADICTED,STALE；confidence只能LOW或MEDIUM；assessment最多约250字，每条rationale最多约90字，只保留最重要的最多4项。"
        "PERSISTING/CHANGED/CONTRADICTED必须引用至少2个轮次；CONTRADICTED必须有明确相反支持，缺失不等于反证；STALE表示只有旧支持、不是错误。"
        "不得宣称执行、不得写入长期记忆、不得把搜索结果提升为事实。ROUNDS=" + context
    )
    a = _unwrap(
        provider("WORLD_CONTINUITY_A", a_prompt), "K.WORLD.CONTINUITY.MODEL.A.1", "proposal_text"
    )
    try:
        proposal = parse_proposal(a["proposal_text"], ids, rsha, current)
    except ContinuityError:
        retry = (
            a_prompt
            + "\nRETRY: 上一候选未通过确定性格式校验。只返回严格JSON；所有ID和SHA必须逐字符来自输入；NEW只能当前轮；STALE不得含当前轮；PERSISTING/CHANGED/CONTRADICTED必须含当前轮和至少一个历史轮。"
        )
        a = _unwrap(
            provider("WORLD_CONTINUITY_A", retry), "K.WORLD.CONTINUITY.MODEL.A.1", "proposal_text"
        )
        proposal = parse_proposal(a["proposal_text"], ids, rsha, current)
    audit_ctx = [
        {
            "observed_at": r["observed_at"],
            "round_context_sha256": r["round_context_sha256"],
            "assessment": r["assessment"],
            "evidence_ids": [x["evidence_id"] for x in r["evidence"]],
        }
        for r in rounds
    ]
    b_prompt = "你是K的跨轮连续性批判层。检查A是否把缺失当反证、把相似标题当同一事实、错误使用NEW/PERSISTING/CHANGED/CONTRADICTED/STALE、或越权形成长期记忆。" "完全合格只回答OK，否则一句简短批判。ROUNDS=" + json.dumps(
        audit_ctx, ensure_ascii=False, separators=(",", ":")
    ) + "\nA=" + json.dumps(
        proposal, ensure_ascii=False, separators=(",", ":")
    )
    b = _unwrap(
        provider("WORLD_CONTINUITY_B", b_prompt), "K.WORLD.CONTINUITY.MODEL.B.1", "critique"
    )
    c_prompt = (
        "你是K的跨轮连续性裁决层。只判断A是否保持临时、可追溯、引用充分，且B没有指出实质错误。合格只回答APPROVE_A，否则只回答REJECT_A。A="
        + json.dumps(proposal, ensure_ascii=False, separators=(",", ":"))
        + "\nB="
        + b["critique"]
    )
    c = _unwrap(provider("WORLD_CONTINUITY_C", c_prompt), "K.WORLD.CONTINUITY.MODEL.C.1", "verdict")
    verdict = c["verdict"]
    if verdict not in {"APPROVE_A", "REJECT_A"}:
        raise ContinuityError("invalid verdict")
    return {
        "schema": "K.WORLD.CONTINUITY.RUN.1",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "source_context_sha256": source_sha,
        "authority": "COGNITIVE_CONTINUITY_PROPOSAL_ONLY",
        "memory_eligible": False,
        "status": "APPROVED_PROVISIONAL" if verdict == "APPROVE_A" else "REJECTED",
        "proposal": proposal,
        "critic": {"critique": b["critique"], "risk_flags": b.get("risk_flags", [])},
        "judge": {"verdict": verdict},
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("one continuity context required")
    print(
        json.dumps(evaluate(sys.argv[1]), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


if __name__ == "__main__":
    main()
