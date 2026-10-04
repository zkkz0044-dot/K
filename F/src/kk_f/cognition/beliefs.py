from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from ..conversation_index import recall_compact, recall_units
from ..fk_audit_protocol import _strict_pairs
from ..k_audit_witness import KAuditWitnessError
from .common import _canonical_obj

_BELIEF_REVISION_KEYS = frozenset(
    {
        "schema",
        "revision_id",
        "belief_id",
        "revision",
        "operation",
        "proposition",
        "status",
        "confidence",
        "prev_revision_sha256",
        "evidence_sequences",
        "reason",
    }
)
_BELIEF_OPERATIONS = frozenset({"CREATE", "UPDATE", "RETRACT", "REOPEN"})
_BELIEF_STATUS = frozenset({"TENTATIVE", "SUPPORTED", "DISPUTED", "UNRESOLVED", "RETRACTED"})
_BELIEF_CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
_ZERO_REVISION_HASH = "0" * 64


def _belief_revision_hash(revision: dict) -> str:
    return hashlib.sha256(_canonical_obj(revision)).hexdigest()


def _parse_belief_revision(event: dict) -> dict:
    try:
        revision = json.loads(event.get("summary", ""), object_pairs_hook=_strict_pairs)
    except Exception as exc:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID") from exc
    if (
        not isinstance(revision, dict)
        or frozenset(revision) != _BELIEF_REVISION_KEYS
        or revision.get("schema") != "K.BELIEF.REVISION.1"
    ):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    for field, limit in (("revision_id", 95), ("belief_id", 63)):
        value = revision.get(field)
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,%d}" % limit, value) is None
        ):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    if type(revision.get("revision")) is not int or revision["revision"] < 1:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    if (
        revision.get("operation") not in _BELIEF_OPERATIONS
        or revision.get("status") not in _BELIEF_STATUS
        or revision.get("confidence") not in _BELIEF_CONFIDENCE
    ):
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
    proposition = revision.get("proposition")
    if (
        not isinstance(proposition, str)
        or not proposition.strip()
        or len(proposition.encode("utf-8")) > 768
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


def _belief_states(events: Iterable[dict]) -> dict[str, dict]:
    current = {}
    for event in events:
        if event.get("subject") != "belief_revision":
            continue
        revision = _parse_belief_revision(event)
        belief_id = revision["belief_id"]
        previous = current.get(belief_id)
        operation = revision["operation"]
        if previous is None:
            if (
                revision["revision"] != 1
                or operation != "CREATE"
                or revision["prev_revision_sha256"] != _ZERO_REVISION_HASH
                or revision["status"] == "RETRACTED"
            ):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        else:
            prior = previous["revision_record"]
            if (
                revision["revision"] != prior["revision"] + 1
                or revision["prev_revision_sha256"] != previous["revision_sha256"]
                or operation == "CREATE"
            ):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            prior_retracted = prior["status"] == "RETRACTED"
            if prior_retracted and operation != "REOPEN":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if not prior_retracted and operation == "REOPEN":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if operation == "RETRACT" and revision["status"] != "RETRACTED":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if operation != "RETRACT" and revision["status"] == "RETRACTED":
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
            if operation == "UPDATE" and all(
                revision[k] == prior[k] for k in ("proposition", "status", "confidence")
            ):
                raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        rhash = _belief_revision_hash(revision)
        current[belief_id] = {
            "revision_record": revision,
            "revision_sha256": rhash,
            "last_event_sequence": event["sequence"],
        }
    return current


def _belief_public(entry: dict) -> dict:
    r = entry["revision_record"]
    return {
        "belief_id": r["belief_id"],
        "revision": r["revision"],
        "proposition": r["proposition"],
        "status": r["status"],
        "confidence": r["confidence"],
        "evidence_sequences": list(r["evidence_sequences"]),
        "revision_sha256": entry["revision_sha256"],
        "last_event_sequence": entry["last_event_sequence"],
    }


def _query_current_beliefs(events: Iterable[dict], query: str, limit: int) -> list[dict]:
    states = _belief_states(events)
    q_units = recall_units(query)
    q_compact = recall_compact(query)
    ranked = []
    for entry in states.values():
        r = entry["revision_record"]
        if r["status"] == "RETRACTED":
            continue
        text = r["belief_id"] + " " + r["proposition"]
        units = recall_units(text)
        compact = recall_compact(text)
        overlap = len(q_units & units)
        phrase = bool(q_compact and len(q_compact) >= 4 and q_compact in compact)
        if overlap == 0 and not phrase:
            continue
        status_weight = {"SUPPORTED": 8, "TENTATIVE": 3, "DISPUTED": 1, "UNRESOLVED": 0}[
            r["status"]
        ]
        confidence_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[r["confidence"]]
        score = overlap * 10 + (80 if phrase else 0) + status_weight + confidence_weight
        ranked.append((score, entry["last_event_sequence"], entry))
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    return [_belief_public(entry) for _score, _seq, entry in ranked[:limit]]


