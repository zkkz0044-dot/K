from __future__ import annotations

import json
import socket
from dataclasses import dataclass

from .memory import verify_event_log

DEFAULT_ADDRESS = "\0kk-fk-audit-v2"
ZERO_DIGEST = "0" * 64
MAX_RESPONSE_BYTES = 16384
RECEIPT_KEYS = frozenset({"schema", "outcome", "generation", "digest"})
VETO_KEYS = frozenset({"schema", "outcome", "reason_code"})


class AuditWitnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuditHead:
    generation: int
    digest: str


def local_audit_head(path: str) -> AuditHead:
    records = verify_event_log(path)
    if not records:
        return AuditHead(0, ZERO_DIGEST)
    return AuditHead(records[-1]["sequence"], records[-1]["entry_sha256"])


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AuditWitnessError("duplicate response key")
        out[key] = value
    return out


def _request(value: dict, address: str) -> dict:
    if not isinstance(address, str) or not address.startswith("\0"):
        raise AuditWitnessError("abstract audit address required")
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(raw) > 4096:
        raise AuditWitnessError("audit request too large")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(3)
        sock.connect(address)
        sock.sendall(raw)
        buf = bytearray()
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > MAX_RESPONSE_BYTES:
                raise AuditWitnessError("audit response too large")
            if b"\n" in chunk:
                break
    except OSError as exc:
        raise AuditWitnessError("audit witness transport failed") from exc
    finally:
        sock.close()
    if not buf.endswith(b"\n") or b"\n" in bytes(buf[:-1]):
        raise AuditWitnessError("invalid audit response framing")
    try:
        response = json.loads(bytes(buf[:-1]).decode("utf-8"), object_pairs_hook=_strict_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise AuditWitnessError("invalid audit response") from exc
    if not isinstance(response, dict):
        raise AuditWitnessError("audit response object required")
    return response


def _parse_receipt(response: dict) -> AuditHead:
    if frozenset(response) == VETO_KEYS:
        if (
            response.get("schema") != "FK_AUDIT.VETO.2"
            or response.get("outcome") != "VETO"
            or not isinstance(response.get("reason_code"), str)
        ):
            raise AuditWitnessError("invalid audit veto")
        raise AuditWitnessError(response["reason_code"])
    if frozenset(response) != RECEIPT_KEYS:
        raise AuditWitnessError("exact audit receipt fields required")
    if response["schema"] != "FK_AUDIT.RECEIPT.2" or response["outcome"] not in {
        "STATE",
        "COMMITTED",
    }:
        raise AuditWitnessError("invalid audit receipt")
    generation = response["generation"]
    digest = response["digest"]
    if type(generation) is not int or generation < 0:
        raise AuditWitnessError("invalid audit generation")
    if not isinstance(digest, str) or len(digest) != 64:
        raise AuditWitnessError("invalid audit digest")
    return AuditHead(generation, digest)


def query_witness(*, address: str = DEFAULT_ADDRESS) -> AuditHead:
    return _parse_receipt(_request({"schema": "FK_AUDIT.QUERY.2"}, address))


def compare_with_witness(path: str, *, address: str = DEFAULT_ADDRESS) -> str:
    records = verify_event_log(path)
    local = (
        AuditHead(0, ZERO_DIGEST)
        if not records
        else AuditHead(records[-1]["sequence"], records[-1]["entry_sha256"])
    )
    remote = query_witness(address=address)
    if local == remote:
        return "MATCH"
    if local.generation < remote.generation:
        return "ROLLBACK_DETECTED"
    if local.generation == remote.generation:
        return "DIVERGENCE"
    if local.generation == remote.generation + 1:
        event = records[-1]
        if event["prev_sha256"] != remote.digest:
            return "FORK_DETECTED"
        return "LOCAL_AHEAD_ONE"
    return "LOCAL_AHEAD_MULTIPLE"


def commit_audit_head(path: str, *, address: str = DEFAULT_ADDRESS) -> AuditHead:
    records = verify_event_log(path)
    if not records:
        raise AuditWitnessError("cannot commit empty audit")
    event = records[-1]
    # Single-shot commit: F independently validates sequence, predecessor and digest.
    # No pre-query is trusted or required, eliminating a query/commit TOCTOU window.
    response = _request({"schema": "FK_AUDIT.COMMIT.2", "event": event}, address)
    committed = _parse_receipt(response)
    expected = AuditHead(event["sequence"], event["entry_sha256"])
    if committed != expected:
        raise AuditWitnessError("committed audit head mismatch")
    return committed


def _build_event_from_head(
    head: AuditHead, *, event_id: str, kind: str, subject: str, summary: str
) -> dict:
    import hashlib
    import re

    event_id_re = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
    if not isinstance(event_id, str) or event_id_re.fullmatch(event_id) is None:
        raise AuditWitnessError("invalid event_id")
    if kind not in {"DECISION", "EXECUTION", "OBSERVATION", "USER_NOTE", "SYSTEM"}:
        raise AuditWitnessError("invalid event kind")
    for value, limit, label in ((subject, 256, "subject"), (summary, 2048, "summary")):
        if not isinstance(value, str) or not (1 <= len(value.encode("utf-8")) <= limit):
            raise AuditWitnessError("invalid event " + label)
    base = {
        "schema": "K02.EVENT.1",
        "sequence": head.generation + 1,
        "event_id": event_id,
        "kind": kind,
        "subject": subject,
        "summary": summary,
        "prev_sha256": head.digest,
    }
    raw = json.dumps(
        base, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    event = dict(base)
    event["entry_sha256"] = hashlib.sha256(raw).hexdigest()
    return event


def append_remote_event(
    *, event_id: str, kind: str, subject: str, summary: str, address: str = DEFAULT_ADDRESS
) -> AuditHead:
    head = query_witness(address=address)
    event = _build_event_from_head(
        head, event_id=event_id, kind=kind, subject=subject, summary=summary
    )
    committed = _parse_receipt(_request({"schema": "FK_AUDIT.COMMIT.2", "event": event}, address))
    expected = AuditHead(event["sequence"], event["entry_sha256"])
    if committed != expected:
        raise AuditWitnessError("remote audit commit mismatch")
    return committed


def remote_soul_audit_sink(address: str = DEFAULT_ADDRESS):
    from .soul_evidence import SoulGateResult, soul_audit_summary

    if not isinstance(address, str) or not address.startswith("\0"):
        raise AuditWitnessError("invalid audit witness address")

    def sink(event_id: str, result: SoulGateResult) -> AuditHead:
        return append_remote_event(
            event_id=event_id,
            kind="SYSTEM",
            subject="soul_gate",
            summary=soul_audit_summary(result),
            address=address,
        )

    return sink


CONVERSATION_SUBJECTS = frozenset(
    {"human_chat", "human_ask", "human_plan", "human_remember", "k_reply"}
)
EVENT_KEYS = frozenset(
    {"schema", "sequence", "event_id", "kind", "subject", "summary", "prev_sha256", "entry_sha256"}
)


def _validate_history_event(value: object) -> dict:
    import hashlib

    if not isinstance(value, dict) or frozenset(value) != EVENT_KEYS:
        raise AuditWitnessError("invalid history event fields")
    if value.get("schema") != "K02.EVENT.1" or value.get("subject") not in CONVERSATION_SUBJECTS:
        raise AuditWitnessError("invalid history event identity")
    if type(value.get("sequence")) is not int or value["sequence"] < 1:
        raise AuditWitnessError("invalid history sequence")
    for field in ("event_id", "kind", "subject", "summary", "prev_sha256", "entry_sha256"):
        if not isinstance(value.get(field), str):
            raise AuditWitnessError("invalid history event type")
    if len(value["summary"].encode("utf-8")) > 2048:
        raise AuditWitnessError("history summary too large")
    base = {
        k: value[k]
        for k in ("schema", "sequence", "event_id", "kind", "subject", "summary", "prev_sha256")
    }
    raw = json.dumps(
        base, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != value["entry_sha256"]:
        raise AuditWitnessError("history event digest mismatch")
    return dict(value)


def query_conversation_history(
    *, limit: int = 8, address: str = DEFAULT_ADDRESS
) -> tuple[dict, ...]:
    if type(limit) is not int or not (1 <= limit <= 8):
        raise AuditWitnessError("invalid history limit")
    response = _request({"schema": "FK_AUDIT.HISTORY.2", "limit": limit}, address)
    if frozenset(response) == VETO_KEYS:
        _parse_receipt(response)
    if not isinstance(response, dict) or frozenset(response) != {"schema", "outcome", "events"}:
        raise AuditWitnessError("exact history response fields required")
    if response["schema"] != "FK_AUDIT.HISTORY.RECEIPT.2" or response["outcome"] != "HISTORY":
        raise AuditWitnessError("invalid history receipt")
    events = response["events"]
    if not isinstance(events, list) or len(events) > limit:
        raise AuditWitnessError("invalid history collection")
    return tuple(_validate_history_event(e) for e in events)


def query_conversation_recall(
    query: str, *, limit: int = 4, address: str = DEFAULT_ADDRESS
) -> tuple[dict, ...]:
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
        raise AuditWitnessError("invalid recall query")
    if type(limit) is not int or not (1 <= limit <= 4):
        raise AuditWitnessError("invalid recall limit")
    response = _request({"schema": "FK_AUDIT.RECALL.2", "query": query, "limit": limit}, address)
    if frozenset(response) == VETO_KEYS:
        _parse_receipt(response)
    if not isinstance(response, dict) or frozenset(response) != {"schema", "outcome", "events"}:
        raise AuditWitnessError("exact recall response fields required")
    if response["schema"] != "FK_AUDIT.RECALL.RECEIPT.2" or response["outcome"] != "RECALL":
        raise AuditWitnessError("invalid recall receipt")
    events = response["events"]
    if not isinstance(events, list) or len(events) > 16:
        raise AuditWitnessError("invalid recall collection")
    checked = tuple(_validate_history_event(e) for e in events)
    if any(checked[i]["sequence"] >= checked[i + 1]["sequence"] for i in range(len(checked) - 1)):
        raise AuditWitnessError("recall events out of order")
    return checked


def query_personality_state(
    core_state: dict, core_sha256: str, *, address: str = DEFAULT_ADDRESS
) -> dict:
    import hashlib

    if (
        not isinstance(core_state, dict)
        or not isinstance(core_sha256, str)
        or len(core_sha256) != 64
    ):
        raise AuditWitnessError("invalid personality core query")
    try:
        raw = json.dumps(
            core_state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AuditWitnessError("invalid personality core query") from exc
    if hashlib.sha256(raw).hexdigest() != core_sha256:
        raise AuditWitnessError("personality core digest mismatch")
    response = _request(
        {"schema": "FK_AUDIT.PERSONALITY.2", "core_sha256": core_sha256, "core_state": core_state},
        address,
    )
    if frozenset(response) == VETO_KEYS:
        _parse_receipt(response)
    keys = {"schema", "outcome", "state", "state_sha256", "revision_count", "last_event_sequence"}
    if not isinstance(response, dict) or frozenset(response) != keys:
        raise AuditWitnessError("exact personality response fields required")
    if (
        response.get("schema") != "FK_AUDIT.PERSONALITY.RECEIPT.2"
        or response.get("outcome") != "PERSONALITY"
    ):
        raise AuditWitnessError("invalid personality receipt")
    if not isinstance(response.get("state"), dict):
        raise AuditWitnessError("invalid personality state")
    state_raw = json.dumps(
        response["state"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if (
        not isinstance(response.get("state_sha256"), str)
        or hashlib.sha256(state_raw).hexdigest() != response["state_sha256"]
    ):
        raise AuditWitnessError("personality state digest mismatch")
    if type(response.get("revision_count")) is not int or response["revision_count"] < 0:
        raise AuditWitnessError("invalid personality revision count")
    if type(response.get("last_event_sequence")) is not int or response["last_event_sequence"] < 0:
        raise AuditWitnessError("invalid personality event sequence")
    return dict(response)


def commit_personality_revision_event(
    core_state: dict,
    core_sha256: str,
    *,
    event_id: str,
    summary: str,
    address: str = DEFAULT_ADDRESS,
) -> AuditHead:
    import hashlib

    if (
        not isinstance(core_state, dict)
        or not isinstance(core_sha256, str)
        or len(core_sha256) != 64
    ):
        raise AuditWitnessError("invalid personality core commit")
    try:
        core_raw = json.dumps(
            core_state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AuditWitnessError("invalid personality core commit") from exc
    if hashlib.sha256(core_raw).hexdigest() != core_sha256:
        raise AuditWitnessError("personality core digest mismatch")
    head = query_witness(address=address)
    event = _build_event_from_head(
        head, event_id=event_id, kind="SYSTEM", subject="personality_revision", summary=summary
    )
    response = _request(
        {
            "schema": "FK_AUDIT.PERSONALITY_COMMIT.2",
            "core_sha256": core_sha256,
            "core_state": core_state,
            "event": event,
        },
        address,
    )
    committed = _parse_receipt(response)
    expected = AuditHead(event["sequence"], event["entry_sha256"])
    if committed != expected:
        raise AuditWitnessError("personality revision commit mismatch")
    return committed


def query_current_beliefs(
    query: str, *, limit: int = 6, address: str = DEFAULT_ADDRESS
) -> tuple[dict, ...]:
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
        raise AuditWitnessError("invalid beliefs query")
    if type(limit) is not int or not (1 <= limit <= 8):
        raise AuditWitnessError("invalid beliefs limit")
    response = _request({"schema": "FK_AUDIT.BELIEFS.2", "query": query, "limit": limit}, address)
    if frozenset(response) == VETO_KEYS:
        _parse_receipt(response)
    if not isinstance(response, dict) or frozenset(response) != {"schema", "outcome", "beliefs"}:
        raise AuditWitnessError("exact beliefs response fields required")
    if (
        response.get("schema") != "FK_AUDIT.BELIEFS.RECEIPT.2"
        or response.get("outcome") != "BELIEFS"
    ):
        raise AuditWitnessError("invalid beliefs receipt")
    beliefs = response.get("beliefs")
    if not isinstance(beliefs, list) or len(beliefs) > limit:
        raise AuditWitnessError("invalid beliefs collection")
    keys = {
        "belief_id",
        "revision",
        "proposition",
        "status",
        "confidence",
        "evidence_sequences",
        "revision_sha256",
        "last_event_sequence",
    }
    out = []
    seen = set()
    for item in beliefs:
        if not isinstance(item, dict) or set(item) != keys:
            raise AuditWitnessError("invalid belief fields")
        bid = item.get("belief_id")
        if not isinstance(bid, str) or not bid or bid in seen:
            raise AuditWitnessError("invalid belief id")
        seen.add(bid)
        if type(item.get("revision")) is not int or item["revision"] < 1:
            raise AuditWitnessError("invalid belief revision")
        if (
            not isinstance(item.get("proposition"), str)
            or not item["proposition"].strip()
            or len(item["proposition"].encode("utf-8")) > 768
        ):
            raise AuditWitnessError("invalid belief proposition")
        if item.get("status") not in {"TENTATIVE", "SUPPORTED", "DISPUTED", "UNRESOLVED"}:
            raise AuditWitnessError("invalid active belief status")
        if item.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            raise AuditWitnessError("invalid belief confidence")
        ev = item.get("evidence_sequences")
        if not isinstance(ev, list) or not ev or any(type(x) is not int or x < 1 for x in ev):
            raise AuditWitnessError("invalid belief evidence")
        if not isinstance(item.get("revision_sha256"), str) or len(item["revision_sha256"]) != 64:
            raise AuditWitnessError("invalid belief digest")
        if type(item.get("last_event_sequence")) is not int or item["last_event_sequence"] < 1:
            raise AuditWitnessError("invalid belief event sequence")
        out.append(dict(item))
    return tuple(out)


def commit_belief_revision_event(
    *, event_id: str, summary: str, address: str = DEFAULT_ADDRESS
) -> AuditHead:
    head = query_witness(address=address)
    event = _build_event_from_head(
        head, event_id=event_id, kind="SYSTEM", subject="belief_revision", summary=summary
    )
    response = _request({"schema": "FK_AUDIT.BELIEF_COMMIT.2", "event": event}, address)
    committed = _parse_receipt(response)
    expected = AuditHead(event["sequence"], event["entry_sha256"])
    if committed != expected:
        raise AuditWitnessError("belief revision commit mismatch")
    return committed


def query_current_skills(
    query: str, *, limit: int = 6, address: str = DEFAULT_ADDRESS
) -> tuple[dict, ...]:
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
        raise AuditWitnessError("invalid skills query")
    if type(limit) is not int or not (1 <= limit <= 8):
        raise AuditWitnessError("invalid skills limit")
    response = _request({"schema": "FK_AUDIT.SKILLS.2", "query": query, "limit": limit}, address)
    if frozenset(response) == VETO_KEYS:
        _parse_receipt(response)
    if not isinstance(response, dict) or frozenset(response) != {"schema", "outcome", "skills"}:
        raise AuditWitnessError("exact skills response fields required")
    if response.get("schema") != "FK_AUDIT.SKILLS.RECEIPT.2" or response.get("outcome") != "SKILLS":
        raise AuditWitnessError("invalid skills receipt")
    skills = response.get("skills")
    if not isinstance(skills, list) or len(skills) > limit:
        raise AuditWitnessError("invalid skills collection")
    keys = {
        "skill_id",
        "revision",
        "description",
        "status",
        "confidence",
        "evidence_sequences",
        "revision_sha256",
        "last_event_sequence",
        "observed_successes",
        "observed_failures",
        "distinct_transfer_contexts",
        "observed_tools",
    }
    out = []
    seen = set()
    for item in skills:
        if not isinstance(item, dict) or set(item) != keys:
            raise AuditWitnessError("invalid skill fields")
        sid = item.get("skill_id")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise AuditWitnessError("invalid skill id")
        seen.add(sid)
        if type(item.get("revision")) is not int or item["revision"] < 1:
            raise AuditWitnessError("invalid skill revision")
        if (
            not isinstance(item.get("description"), str)
            or not item["description"].strip()
            or len(item["description"].encode("utf-8")) > 768
        ):
            raise AuditWitnessError("invalid skill description")
        if item.get("status") not in {"CANDIDATE", "VALIDATED", "DEGRADED"}:
            raise AuditWitnessError("invalid active skill status")
        if item.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            raise AuditWitnessError("invalid skill confidence")
        ev = item.get("evidence_sequences")
        if not isinstance(ev, list) or not ev or any(type(x) is not int or x < 1 for x in ev):
            raise AuditWitnessError("invalid skill evidence")
        if not isinstance(item.get("revision_sha256"), str) or len(item["revision_sha256"]) != 64:
            raise AuditWitnessError("invalid skill digest")
        if type(item.get("last_event_sequence")) is not int or item["last_event_sequence"] < 1:
            raise AuditWitnessError("invalid skill event sequence")
        for key in ("observed_successes", "observed_failures", "distinct_transfer_contexts"):
            if type(item.get(key)) is not int or item[key] < 0:
                raise AuditWitnessError("invalid skill metric")
        tools = item.get("observed_tools")
        if not isinstance(tools, list) or any(not isinstance(x, str) or not x for x in tools):
            raise AuditWitnessError("invalid skill tools")
        out.append(dict(item))
    return tuple(out)


def commit_skill_revision_event(
    *, event_id: str, summary: str, address: str = DEFAULT_ADDRESS
) -> AuditHead:
    head = query_witness(address=address)
    event = _build_event_from_head(
        head, event_id=event_id, kind="SYSTEM", subject="skill_revision", summary=summary
    )
    response = _request({"schema": "FK_AUDIT.SKILL_COMMIT.2", "event": event}, address)
    committed = _parse_receipt(response)
    expected = AuditHead(event["sequence"], event["entry_sha256"])
    if committed != expected:
        raise AuditWitnessError("skill revision commit mismatch")
    return committed
