from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass

from .authority_guard import AuthorityGuardError, read_root_authority
from .audit_witness import (
    AuditWitnessError,
    commit_personality_revision_event,
    query_personality_state,
)

CORE_SCHEMA = "K.PERSONALITY.CORE.1"
TRAIT_NAMES = ("curiosity", "directness", "warmth", "skepticism", "risk_tolerance")
CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
PLASTICITY = frozenset({"SLOW"})
CORE_KEYS = frozenset(
    {
        "schema",
        "identity_id",
        "version",
        "formation_state",
        "model_is_personality",
        "change_policy",
        "history_policy",
        "traits",
    }
)
TRAIT_KEYS = frozenset({"value", "confidence", "plasticity"})
DEFAULT_PATH = "/root/K/K/config/personality_core.json"


class PersonalityError(ValueError):
    pass


@dataclass(frozen=True)
class PersonalitySnapshot:
    state: dict
    sha256: str
    revision_count: int = 0
    last_event_sequence: int = 0


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise PersonalityError("duplicate personality key")
        out[key] = value
    return out


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PersonalityError("non-canonical personality value") from exc


def personality_sha256(state: dict) -> str:
    return hashlib.sha256(_canonical(validate_personality(state))).hexdigest()


def validate_personality(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != CORE_KEYS:
        raise PersonalityError("exact personality core fields required")
    if value.get("schema") != CORE_SCHEMA or value.get("identity_id") != "KK-K":
        raise PersonalityError("personality identity mismatch")
    if type(value.get("version")) is not int or value["version"] < 1:
        raise PersonalityError("invalid personality version")
    if value.get("formation_state") not in {"UNDER_CULTIVATION", "FORMED", "MATURE_EVOLVING"}:
        raise PersonalityError("invalid personality formation state")
    if value.get("model_is_personality") is not False:
        raise PersonalityError("model cannot be personality")
    if value.get("change_policy") != "SLOW_APPEND_ONLY_EVIDENCE_LINKED":
        raise PersonalityError("invalid personality change policy")
    if value.get("history_policy") != "PRIOR_VERSIONS_PRESERVED":
        raise PersonalityError("invalid personality history policy")
    traits = value.get("traits")
    if not isinstance(traits, dict) or tuple(sorted(traits)) != tuple(sorted(TRAIT_NAMES)):
        raise PersonalityError("exact personality traits required")
    checked_traits = {}
    for name in TRAIT_NAMES:
        trait = traits[name]
        if not isinstance(trait, dict) or frozenset(trait) != TRAIT_KEYS:
            raise PersonalityError("exact trait fields required")
        text = trait.get("value")
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 128:
            raise PersonalityError("invalid trait value")
        if trait.get("confidence") not in CONFIDENCE or trait.get("plasticity") not in PLASTICITY:
            raise PersonalityError("invalid trait policy")
        checked_traits[name] = dict(trait)
    out = dict(value)
    out["traits"] = checked_traits
    return out


def load_personality_core(path: str = DEFAULT_PATH) -> PersonalitySnapshot:
    try:
        raw = read_root_authority(path, max_bytes=8192)
    except AuthorityGuardError as exc:
        raise PersonalityError("personality authority rejected") from exc
    try:
        value = json.loads(raw, object_pairs_hook=_strict_pairs)
    except PersonalityError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise PersonalityError("invalid personality JSON") from exc
    state = validate_personality(value)
    return PersonalitySnapshot(state=state, sha256=hashlib.sha256(_canonical(state)).hexdigest())


def prompt_view(snapshot: PersonalitySnapshot) -> dict:
    if not isinstance(snapshot, PersonalitySnapshot):
        raise PersonalityError("validated personality snapshot required")
    state = validate_personality(snapshot.state)
    traits = {name: dict(state["traits"][name]) for name in TRAIT_NAMES}
    return {
        "schema": "K.PERSONALITY.PROMPT_VIEW.1",
        "version": state["version"],
        "formation_state": state["formation_state"],
        "traits": traits,
        "revision_count": snapshot.revision_count,
        "last_event_sequence": snapshot.last_event_sequence,
        "authority": "SELF_STATE_NOT_FACT_AUTHORITY",
    }


def load_personality_snapshot(
    path: str = DEFAULT_PATH, *, address: str = "\0kk-fk-audit-v2"
) -> PersonalitySnapshot:
    core = load_personality_core(path)
    try:
        receipt = query_personality_state(core.state, core.sha256, address=address)
    except AuditWitnessError as exc:
        raise PersonalityError("personality witness rejected") from exc
    state = validate_personality(receipt["state"])
    digest = personality_sha256(state)
    if digest != receipt["state_sha256"]:
        raise PersonalityError("personality witness digest mismatch")
    count = receipt["revision_count"]
    if state["version"] != core.state["version"] + count:
        raise PersonalityError("personality version/revision mismatch")
    if count == 0 and (
        digest != core.sha256 or state != core.state or receipt["last_event_sequence"] != 0
    ):
        raise PersonalityError("personality zero-revision mismatch")
    return PersonalitySnapshot(
        state=state,
        sha256=digest,
        revision_count=count,
        last_event_sequence=receipt["last_event_sequence"],
    )


def build_personality_revision(
    snapshot: PersonalitySnapshot,
    *,
    trait: str,
    value: str,
    confidence: str,
    evidence_sequences: tuple[int, ...] | list[int],
    reason: str,
    formation_state: str | None = None,
    revision_id: str | None = None,
) -> tuple[dict, str]:
    if not isinstance(snapshot, PersonalitySnapshot):
        raise PersonalityError("validated personality snapshot required")
    current = validate_personality(snapshot.state)
    if trait not in TRAIT_NAMES:
        raise PersonalityError("unknown personality trait")
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 128:
        raise PersonalityError("invalid personality trait value")
    if confidence not in CONFIDENCE:
        raise PersonalityError("invalid personality confidence")
    evidence = list(evidence_sequences) if isinstance(evidence_sequences, (tuple, list)) else None
    if (
        evidence is None
        or not (3 <= len(evidence) <= 32)
        or len(set(evidence)) != len(evidence)
        or any(type(x) is not int or x < 1 for x in evidence)
    ):
        raise PersonalityError("personality revision requires distinct evidence sequences")
    if not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-8")) > 512:
        raise PersonalityError("invalid personality revision reason")
    next_state = json.loads(json.dumps(current, ensure_ascii=False))
    next_state["version"] = current["version"] + 1
    if formation_state is not None:
        next_state["formation_state"] = formation_state
    next_state["traits"][trait]["value"] = value.strip()
    next_state["traits"][trait]["confidence"] = confidence
    next_state = validate_personality(next_state)
    if (
        next_state["traits"][trait] == current["traits"][trait]
        and next_state["formation_state"] == current["formation_state"]
    ):
        raise PersonalityError("personality revision must change state")
    rid = revision_id or ("personality-" + secrets.token_hex(8))
    if not isinstance(rid, str) or not rid or len(rid) > 96:
        raise PersonalityError("invalid personality revision id")
    revision = {
        "schema": "K.PERSONALITY.REVISION.1",
        "revision_id": rid,
        "version": next_state["version"],
        "prev_state_sha256": snapshot.sha256,
        "state": next_state,
        "evidence_sequences": evidence,
        "reason": reason.strip(),
    }
    summary = json.dumps(
        revision, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    if len(summary.encode("utf-8")) > 2048:
        raise PersonalityError("personality revision exceeds audit event budget")
    return next_state, summary


def commit_personality_revision(
    snapshot: PersonalitySnapshot,
    *,
    trait: str,
    value: str,
    confidence: str,
    evidence_sequences: tuple[int, ...] | list[int],
    reason: str,
    formation_state: str | None = None,
    address: str = "\0kk-fk-audit-v2",
) -> PersonalitySnapshot:
    next_state, summary = build_personality_revision(
        snapshot,
        trait=trait,
        value=value,
        confidence=confidence,
        evidence_sequences=evidence_sequences,
        reason=reason,
        formation_state=formation_state,
    )
    event_id = "personality-" + secrets.token_hex(8)
    core = load_personality_core()
    try:
        commit_personality_revision_event(
            core.state, core.sha256, event_id=event_id, summary=summary, address=address
        )
    except AuditWitnessError as exc:
        raise PersonalityError("personality revision commit rejected") from exc
    updated = load_personality_snapshot(address=address)
    if updated.state != next_state or updated.revision_count != snapshot.revision_count + 1:
        raise PersonalityError("personality revision post-commit mismatch")
    return updated
