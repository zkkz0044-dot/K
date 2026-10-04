from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from ..conversation_index import recall_compact, recall_units
from ..fk_audit_protocol import _strict_pairs
from ..k_audit_witness import KAuditWitnessError
from .common import _canonical_obj

_SKILL_REVISION_KEYS = frozenset(
    {
        "schema",
        "revision_id",
        "skill_id",
        "revision",
        "operation",
        "description",
        "status",
        "confidence",
        "prev_revision_sha256",
        "evidence_sequences",
        "reason",
    }
)
_SKILL_OPERATIONS = frozenset({"CREATE", "UPDATE", "VALIDATE", "DEGRADE", "REVOKE", "REOPEN"})
_SKILL_STATUS = frozenset({"CANDIDATE", "VALIDATED", "DEGRADED", "REVOKED"})
_SKILL_CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
_SKILL_ZERO_HASH = "0" * 64
_HUMAN_SUBJECTS = frozenset({"human_chat", "human_ask", "human_plan", "human_remember"})


def _skill_revision_hash(revision: dict) -> str:
    return hashlib.sha256(_canonical_obj(revision)).hexdigest()


def _capability_proof(event: dict, context_id: str | None) -> dict | None:
    if event.get("subject") != "capability_evidence":
        return None
    try:
        value = json.loads(event.get("summary", ""), object_pairs_hook=_strict_pairs)
    except Exception:
        return None
    if not isinstance(value, dict):
        return None
    schema = value.get("schema")
    if schema == "K.COGNITION.CAPABILITY_AUDIT.1":
        tool = value.get("tool")
        reason = value.get("reason")
        verdict = value.get("verdict")
        verified = value.get("verified")
        executed = value.get("executed")
        receipt_sha = value.get("receipt_sha256")
    elif schema == "K.COGNITION.CAPABILITY_EVIDENCE.1":
        receipt = value.get("receipt") if isinstance(value.get("receipt"), dict) else {}
        tool = value.get("tool")
        reason = value.get("reason")
        verdict = value.get("verdict")
        verified = receipt.get("verified")
        executed = receipt.get("executed")
        receipt_sha = hashlib.sha256(_canonical_obj(value)).hexdigest()
    else:
        return None
    if not isinstance(tool, str) or not tool or not isinstance(reason, str) or not reason:
        return None
    if not isinstance(receipt_sha, str) or re.fullmatch(r"[0-9a-f]{64}", receipt_sha) is None:
        return None
    success = verdict == "PASS" and verified is True and executed is True
    negative = verdict in {"VETO", "FAIL"} or verified is False or executed is False
    if not success and not negative:
        return None
    return {
        "sequence": event.get("sequence"),
        "tool": tool,
        "reason": reason,
        "receipt_sha256": receipt_sha,
        "context_id": context_id,
        "success": success,
        "negative": negative,
    }


def _parse_skill_revision(event: dict) -> dict:
    try:
        revision = json.loads(event.get("summary", ""), object_pairs_hook=_strict_pairs)
    except Exception as exc:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID") from exc
    if (
        not isinstance(revision, dict)
        or frozenset(revision) != _SKILL_REVISION_KEYS
        or revision.get("schema") != "K.SKILL.REVISION.1"
    ):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    for field, limit in (("revision_id", 95), ("skill_id", 63)):
        value = revision.get(field)
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,%d}" % limit, value) is None
        ):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    if type(revision.get("revision")) is not int or revision["revision"] < 1:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    if (
        revision.get("operation") not in _SKILL_OPERATIONS
        or revision.get("status") not in _SKILL_STATUS
        or revision.get("confidence") not in _SKILL_CONFIDENCE
    ):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    description = revision.get("description")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description.encode("utf-8")) > 768
    ):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    prev_hash = revision.get("prev_revision_sha256")
    if not isinstance(prev_hash, str) or re.fullmatch(r"[0-9a-f]{64}", prev_hash) is None:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    evidence = revision.get("evidence_sequences")
    seq = event.get("sequence")
    if (
        not isinstance(evidence, list)
        or not (1 <= len(evidence) <= 32)
        or len(set(evidence)) != len(evidence)
    ):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    if any(type(x) is not int or x < 1 or x >= seq for x in evidence):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    reason = revision.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-8")) > 512:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    return revision


def _skill_states(events: Iterable[dict]) -> dict[str, dict]:
    current = {}
    proofs = {}
    context_id = None
    for event in events:
        subject = event.get("subject")
        if subject in _HUMAN_SUBJECTS:
            raw = (subject + "\n" + str(event.get("summary", ""))).encode("utf-8")
            context_id = hashlib.sha256(raw).hexdigest()
        proof = _capability_proof(event, context_id)
        if proof is not None:
            proofs[event["sequence"]] = proof
        if subject != "skill_revision":
            continue
        revision = _parse_skill_revision(event)
        refs = revision["evidence_sequences"]
        if any(x not in proofs for x in refs):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        selected = [proofs[x] for x in refs]
        success_now = [p for p in selected if p["success"]]
        negative_now = [p for p in selected if p["negative"]]
        skill_id = revision["skill_id"]
        previous = current.get(skill_id)
        op = revision["operation"]
        if previous is None:
            if (
                revision["revision"] != 1
                or op != "CREATE"
                or revision["status"] != "CANDIDATE"
                or revision["prev_revision_sha256"] != _SKILL_ZERO_HASH
                or not success_now
            ):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            success_sequences = set()
            contexts = set()
            receipts = set()
            tools = set()
            negative_sequences = set()
        else:
            prior = previous["revision_record"]
            if (
                revision["revision"] != prior["revision"] + 1
                or revision["prev_revision_sha256"] != previous["revision_sha256"]
                or op == "CREATE"
            ):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if prior["status"] == "REVOKED" and op != "REOPEN":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if prior["status"] != "REVOKED" and op == "REOPEN":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if op == "VALIDATE" and revision["status"] != "VALIDATED":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if op == "DEGRADE" and (
                prior["status"] != "VALIDATED"
                or revision["status"] != "DEGRADED"
                or not negative_now
                or revision["confidence"] == "HIGH"
            ):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if op == "REVOKE" and (revision["status"] != "REVOKED" or not negative_now):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if op == "REOPEN" and (revision["status"] != "CANDIDATE" or not success_now):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if op == "UPDATE" and revision["status"] != prior["status"]:
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            success_sequences = set(previous["success_sequences"])
            contexts = set(previous["contexts"])
            receipts = set(previous["receipts"])
            tools = set(previous["tools"])
            negative_sequences = set(previous["negative_sequences"])
        for p in selected:
            if p["success"]:
                success_sequences.add(p["sequence"])
                receipts.add(p["receipt_sha256"])
                tools.add(p["tool"])
                if p["context_id"]:
                    contexts.add(p["context_id"])
            if p["negative"]:
                negative_sequences.add(p["sequence"])
        if op == "VALIDATE":
            if len(success_sequences) < 3 or len(contexts) < 3 or len(receipts) < 3:
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        rhash = _skill_revision_hash(revision)
        current[skill_id] = {
            "revision_record": revision,
            "revision_sha256": rhash,
            "last_event_sequence": event["sequence"],
            "success_sequences": success_sequences,
            "negative_sequences": negative_sequences,
            "contexts": contexts,
            "receipts": receipts,
            "tools": tools,
        }
    return current


def _skill_public(entry: dict) -> dict:
    r = entry["revision_record"]
    return {
        "skill_id": r["skill_id"],
        "revision": r["revision"],
        "description": r["description"],
        "status": r["status"],
        "confidence": r["confidence"],
        "evidence_sequences": list(r["evidence_sequences"]),
        "revision_sha256": entry["revision_sha256"],
        "last_event_sequence": entry["last_event_sequence"],
        "observed_successes": len(entry["success_sequences"]),
        "observed_failures": len(entry["negative_sequences"]),
        "distinct_transfer_contexts": len(entry["contexts"]),
        "observed_tools": sorted(entry["tools"]),
    }


def _query_current_skills(events: Iterable[dict], query: str, limit: int) -> list[dict]:
    states = _skill_states(events)
    q_units = recall_units(query)
    q_compact = recall_compact(query)
    ranked = []
    for entry in states.values():
        r = entry["revision_record"]
        if r["status"] == "REVOKED":
            continue
        text = r["skill_id"] + " " + r["description"] + " " + " ".join(entry["tools"])
        units = recall_units(text)
        compact = recall_compact(text)
        overlap = len(q_units & units)
        phrase = bool(q_compact and len(q_compact) >= 4 and q_compact in compact)
        if overlap == 0 and not phrase:
            continue
        status_weight = {"VALIDATED": 12, "CANDIDATE": 4, "DEGRADED": 1}[r["status"]]
        confidence_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[r["confidence"]]
        score = (
            overlap * 10
            + (80 if phrase else 0)
            + status_weight
            + confidence_weight
            + min(5, len(entry["contexts"]))
        )
        ranked.append((score, entry["last_event_sequence"], entry))
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    return [_skill_public(entry) for _score, _seq, entry in ranked[:limit]]
