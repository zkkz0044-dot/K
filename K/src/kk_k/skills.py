from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass

from .audit_witness import DEFAULT_ADDRESS, AuditWitnessError, commit_skill_revision_event, query_current_skills

STATUS = frozenset({"CANDIDATE", "VALIDATED", "DEGRADED", "REVOKED"})
CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
OPERATIONS = frozenset({"CREATE", "UPDATE", "VALIDATE", "DEGRADE", "REVOKE", "REOPEN"})
SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ZERO_HASH = "0" * 64


class SkillError(ValueError):
    pass


@dataclass(frozen=True)
class SkillRevision:
    state: dict
    sha256: str


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SkillError("non-canonical skill value") from exc


def _evidence(values) -> list[int]:
    if not isinstance(values, (tuple, list)):
        raise SkillError("skill evidence list required")
    out = list(values)
    if (
        not (1 <= len(out) <= 32)
        or len(set(out)) != len(out)
        or any(type(x) is not int or x < 1 for x in out)
    ):
        raise SkillError("invalid skill evidence sequences")
    return out


def build_revision(
    *,
    skill_id: str,
    description: str,
    status: str,
    confidence: str,
    evidence_sequences,
    reason: str,
    previous: dict | None = None,
    operation: str | None = None,
    revision_id: str | None = None,
) -> SkillRevision:
    if not isinstance(skill_id, str) or SKILL_ID_RE.fullmatch(skill_id) is None:
        raise SkillError("invalid skill id")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description.encode("utf-8")) > 768
    ):
        raise SkillError("invalid skill description")
    if status not in STATUS or confidence not in CONFIDENCE:
        raise SkillError("invalid skill status/confidence")
    evidence = _evidence(evidence_sequences)
    if not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-8")) > 512:
        raise SkillError("invalid skill reason")
    if previous is None:
        op = operation or "CREATE"
        if op != "CREATE" or status != "CANDIDATE":
            raise SkillError("first skill revision must CREATE CANDIDATE")
        revision = 1
        prev_hash = ZERO_HASH
    else:
        if not isinstance(previous, dict) or previous.get("skill_id") != skill_id:
            raise SkillError("skill predecessor mismatch")
        if type(previous.get("revision")) is not int or previous["revision"] < 1:
            raise SkillError("invalid skill predecessor revision")
        prev_hash = previous.get("revision_sha256")
        if not isinstance(prev_hash, str) or re.fullmatch(r"[0-9a-f]{64}", prev_hash) is None:
            raise SkillError("invalid skill predecessor digest")
        op = operation or "UPDATE"
        if op not in OPERATIONS or op == "CREATE":
            raise SkillError("invalid skill update operation")
        prior_status = previous.get("status")
        if prior_status == "REVOKED" and op != "REOPEN":
            raise SkillError("revoked skill requires REOPEN")
        if prior_status != "REVOKED" and op == "REOPEN":
            raise SkillError("REOPEN requires revoked predecessor")
        required = {
            "VALIDATE": "VALIDATED",
            "DEGRADE": "DEGRADED",
            "REVOKE": "REVOKED",
            "REOPEN": "CANDIDATE",
        }.get(op)
        if required is not None and status != required:
            raise SkillError("skill operation/status mismatch")
        if op == "UPDATE" and status != prior_status:
            raise SkillError("UPDATE cannot change skill status")
        revision = previous["revision"] + 1
    rid = revision_id or ("skill-" + secrets.token_hex(8))
    if not isinstance(rid, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", rid) is None:
        raise SkillError("invalid skill revision id")
    state = {
        "schema": "K.SKILL.REVISION.1",
        "revision_id": rid,
        "skill_id": skill_id,
        "revision": revision,
        "operation": op,
        "description": description.strip(),
        "status": status,
        "confidence": confidence,
        "prev_revision_sha256": prev_hash,
        "evidence_sequences": evidence,
        "reason": reason.strip(),
    }
    raw = _canonical(state)
    if len(raw) > 2048:
        raise SkillError("skill revision exceeds audit event budget")
    return SkillRevision(state=state, sha256=hashlib.sha256(raw).hexdigest())


def commit_revision(revision: SkillRevision, *, address: str = DEFAULT_ADDRESS) -> None:
    if not isinstance(revision, SkillRevision):
        raise SkillError("validated skill revision required")
    try:
        commit_skill_revision_event(
            event_id=revision.state["revision_id"],
            summary=_canonical(revision.state).decode("utf-8"),
            address=address,
        )
    except AuditWitnessError as exc:
        raise SkillError("skill revision commit rejected") from exc


def current_skills(
    query: str, *, limit: int = 6, address: str = DEFAULT_ADDRESS
) -> tuple[dict, ...]:
    try:
        return query_current_skills(query, limit=limit, address=address)
    except AuditWitnessError as exc:
        raise SkillError("skill query rejected") from exc


def prompt_view(skills: tuple[dict, ...] | list[dict]) -> dict:
    items = []
    keys = (
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
    )
    for item in skills:
        if not isinstance(item, dict):
            raise SkillError("validated skill item required")
        items.append({k: item[k] for k in keys})
    return {
        "schema": "K.SKILL.PROMPT_VIEW.1",
        "authority": "OBSERVED_EXECUTION_CAPABILITY_NOT_GUARANTEE",
        "skills": items,
    }
