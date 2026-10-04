from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from ..fk_audit_protocol import _strict_pairs
from ..k_audit_witness import KAuditWitnessError
from .common import _canonical_obj

_PERSONALITY_REVISION_KEYS = frozenset(
    {
        "schema",
        "revision_id",
        "version",
        "prev_state_sha256",
        "state",
        "evidence_sequences",
        "reason",
    }
)
_PERSONALITY_IMMUTABLE = (
    "schema",
    "identity_id",
    "model_is_personality",
    "change_policy",
    "history_policy",
)
_FORMATION_ORDER = {"UNDER_CULTIVATION": 0, "FORMED": 1, "MATURE_EVOLVING": 2}




def _one_trait_transition(previous: dict, current: dict) -> bool:
    if (
        not isinstance(previous, dict)
        or not isinstance(current, dict)
        or set(previous) != set(current)
    ):
        return False
    for key in _PERSONALITY_IMMUTABLE:
        if current.get(key) != previous.get(key):
            return False
    if (
        type(previous.get("version")) is not int
        or current.get("version") != previous["version"] + 1
    ):
        return False
    a = _FORMATION_ORDER.get(previous.get("formation_state"))
    b = _FORMATION_ORDER.get(current.get("formation_state"))
    if a is None or b is None or b < a or b > a + 1:
        return False
    old_traits = previous.get("traits")
    new_traits = current.get("traits")
    if (
        not isinstance(old_traits, dict)
        or not isinstance(new_traits, dict)
        or set(old_traits) != set(new_traits)
    ):
        return False
    changed = []
    for name in old_traits:
        old = old_traits[name]
        new = new_traits[name]
        if not isinstance(old, dict) or not isinstance(new, dict) or set(old) != set(new):
            return False
        if old.get("plasticity") != new.get("plasticity"):
            return False
        if old != new:
            changed.append(name)
    return len(changed) == 1


def _personality_state(events: Iterable[dict], core_state: dict, core_sha256: str) -> dict:
    previous = json.loads(json.dumps(core_state, ensure_ascii=False))
    expected_hash = core_sha256
    count = 0
    last_sequence = 0
    for event in events:
        if event.get("subject") != "personality_revision":
            continue
        try:
            revision = json.loads(event.get("summary", ""), object_pairs_hook=_strict_pairs)
        except Exception as exc:
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID") from exc
        if (
            not isinstance(revision, dict)
            or frozenset(revision) != _PERSONALITY_REVISION_KEYS
            or revision.get("schema") != "K.PERSONALITY.REVISION.1"
        ):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        rid = revision.get("revision_id")
        if (
            not isinstance(rid, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", rid) is None
        ):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        state = revision.get("state")
        if not _one_trait_transition(previous, state):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        if (
            revision.get("version") != state.get("version")
            or revision.get("prev_state_sha256") != expected_hash
        ):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        evidence = revision.get("evidence_sequences")
        if (
            not isinstance(evidence, list)
            or not (3 <= len(evidence) <= 32)
            or len(set(evidence)) != len(evidence)
        ):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        seq = event.get("sequence")
        if any(type(x) is not int or x < 1 or x >= seq for x in evidence):
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        reason = revision.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-8")) > 512:
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        if count and seq - last_sequence < 20:
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")
        expected_hash = hashlib.sha256(_canonical_obj(state)).hexdigest()
        previous = state
        count += 1
        last_sequence = seq
    return {
        "schema": "FK_AUDIT.PERSONALITY.RECEIPT.2",
        "outcome": "PERSONALITY",
        "state": previous,
        "state_sha256": expected_hash,
        "revision_count": count,
        "last_event_sequence": last_sequence,
    }


