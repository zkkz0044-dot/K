from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass

from .audit_witness import DEFAULT_ADDRESS, AuditWitnessError, commit_belief_revision_event, query_current_beliefs

STATUS = frozenset({"TENTATIVE", "SUPPORTED", "DISPUTED", "UNRESOLVED", "RETRACTED"})
CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
OPERATIONS = frozenset({"CREATE", "UPDATE", "RETRACT", "REOPEN"})
BELIEF_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ZERO_HASH = "0" * 64


class BeliefError(ValueError):
    pass


@dataclass(frozen=True)
class BeliefRevision:
    state: dict
    sha256: str


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BeliefError("non-canonical belief value") from exc


def _validate_evidence(evidence_sequences) -> list[int]:
    if not isinstance(evidence_sequences, (tuple, list)):
        raise BeliefError("belief evidence list required")
    evidence = list(evidence_sequences)
    if (
        not (1 <= len(evidence) <= 32)
        or len(set(evidence)) != len(evidence)
        or any(type(x) is not int or x < 1 for x in evidence)
    ):
        raise BeliefError("invalid belief evidence sequences")
    return evidence


def build_revision(
    *,
    belief_id: str,
    proposition: str,
    status: str,
    confidence: str,
    evidence_sequences,
    reason: str,
    previous: dict | None = None,
    operation: str | None = None,
    revision_id: str | None = None,
) -> BeliefRevision:
    if not isinstance(belief_id, str) or BELIEF_ID_RE.fullmatch(belief_id) is None:
        raise BeliefError("invalid belief id")
    if (
        not isinstance(proposition, str)
        or not proposition.strip()
        or len(proposition.encode("utf-8")) > 768
    ):
        raise BeliefError("invalid belief proposition")
    if status not in STATUS or confidence not in CONFIDENCE:
        raise BeliefError("invalid belief status/confidence")
    evidence = _validate_evidence(evidence_sequences)
    if not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-8")) > 512:
        raise BeliefError("invalid belief reason")
    if previous is None:
        op = operation or "CREATE"
        if op != "CREATE" or status == "RETRACTED":
            raise BeliefError("first belief revision must CREATE an active belief")
        revision = 1
        prev_hash = ZERO_HASH
    else:
        if not isinstance(previous, dict) or previous.get("belief_id") != belief_id:
            raise BeliefError("belief predecessor mismatch")
        if type(previous.get("revision")) is not int or previous["revision"] < 1:
            raise BeliefError("invalid belief predecessor revision")
        prev_hash = previous.get("revision_sha256")
        if not isinstance(prev_hash, str) or re.fullmatch(r"[0-9a-f]{64}", prev_hash) is None:
            raise BeliefError("invalid belief predecessor digest")
        op = operation or "UPDATE"
        if op not in OPERATIONS or op == "CREATE":
            raise BeliefError("invalid belief update operation")
        if previous.get("status") == "RETRACTED" and op != "REOPEN":
            raise BeliefError("retracted belief requires REOPEN")
        if previous.get("status") != "RETRACTED" and op == "REOPEN":
            raise BeliefError("REOPEN requires retracted predecessor")
        if op == "RETRACT" and status != "RETRACTED":
            raise BeliefError("RETRACT must produce RETRACTED status")
        if op != "RETRACT" and status == "RETRACTED":
            raise BeliefError("RETRACTED status requires RETRACT")
        revision = previous["revision"] + 1
    rid = revision_id or ("belief-" + secrets.token_hex(8))
    if not isinstance(rid, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", rid) is None:
        raise BeliefError("invalid belief revision id")
    state = {
        "schema": "K.BELIEF.REVISION.1",
        "revision_id": rid,
        "belief_id": belief_id,
        "revision": revision,
        "operation": op,
        "proposition": proposition.strip(),
        "status": status,
        "confidence": confidence,
        "prev_revision_sha256": prev_hash,
        "evidence_sequences": evidence,
        "reason": reason.strip(),
    }
    raw = _canonical(state)
    if len(raw) > 2048:
        raise BeliefError("belief revision exceeds audit event budget")
    return BeliefRevision(state=state, sha256=hashlib.sha256(raw).hexdigest())


def commit_revision(revision: BeliefRevision, *, address: str = DEFAULT_ADDRESS) -> None:
    if not isinstance(revision, BeliefRevision):
        raise BeliefError("validated belief revision required")
    summary = _canonical(revision.state).decode("utf-8")
    try:
        commit_belief_revision_event(
            event_id=revision.state["revision_id"], summary=summary, address=address
        )
    except AuditWitnessError as exc:
        raise BeliefError("belief revision commit rejected") from exc


def current_beliefs(
    query: str, *, limit: int = 6, address: str = DEFAULT_ADDRESS
) -> tuple[dict, ...]:
    try:
        return query_current_beliefs(query, limit=limit, address=address)
    except AuditWitnessError as exc:
        raise BeliefError("belief query rejected") from exc


def prompt_view(beliefs: tuple[dict, ...] | list[dict]) -> dict:
    items = []
    for item in beliefs:
        if not isinstance(item, dict):
            raise BeliefError("validated belief item required")
        items.append(
            {
                k: item[k]
                for k in (
                    "belief_id",
                    "revision",
                    "proposition",
                    "status",
                    "confidence",
                    "evidence_sequences",
                    "revision_sha256",
                    "last_event_sequence",
                )
            }
        )
    return {
        "schema": "K.BELIEF.PROMPT_VIEW.1",
        "authority": "REVISABLE_SELF_BELIEF_NOT_FACT_AUTHORITY",
        "beliefs": items,
    }
