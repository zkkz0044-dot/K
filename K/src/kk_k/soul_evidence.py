from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .action_registry import ALLOWED_ACTIONS
from .memory import append_event
from .souls import SoulDecision

EVIDENCE_KEYS = frozenset(
    {
        "schema",
        "evidence_id",
        "source_id",
        "trust",
        "freshness",
        "stance",
        "actions",
        "claim",
    }
)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
FRESHNESS = frozenset({"FRESH", "STALE", "UNKNOWN"})
STANCE = frozenset({"SUPPORT", "CONTRADICT"})
MAX_EVIDENCE_ITEMS = 16
MAX_CLAIM_BYTES = 1024


class SoulEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class SoulGateResult:
    requested_action_id: str
    governed_candidate_id: str
    outcome: str
    reason: str
    decision_sha256: str
    evidence_sha256: str


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SoulEvidenceError("non-canonical evidence") from exc


def _validate_item(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != EVIDENCE_KEYS:
        raise SoulEvidenceError("exact evidence fields required")
    if value["schema"] != "KS02.EVIDENCE.1":
        raise SoulEvidenceError("unsupported evidence schema")
    for key in ("evidence_id", "source_id"):
        if not isinstance(value[key], str) or ID_RE.fullmatch(value[key]) is None:
            raise SoulEvidenceError(f"invalid {key}")
    if value["trust"] != "UNTRUSTED_EVIDENCE":
        raise SoulEvidenceError("evidence trust escalation forbidden")
    if value["freshness"] not in FRESHNESS:
        raise SoulEvidenceError("invalid evidence freshness")
    if value["stance"] not in STANCE:
        raise SoulEvidenceError("invalid evidence stance")
    actions = value["actions"]
    if not isinstance(actions, list) or not (1 <= len(actions) <= 5):
        raise SoulEvidenceError("invalid evidence actions")
    if any(not isinstance(action, str) or action not in ALLOWED_ACTIONS for action in actions):
        raise SoulEvidenceError("unknown evidence action")
    if len(set(actions)) != len(actions):
        raise SoulEvidenceError("duplicate evidence action")
    claim = value["claim"]
    if not isinstance(claim, str) or len(claim.encode("utf-8")) > MAX_CLAIM_BYTES:
        raise SoulEvidenceError("invalid evidence claim")
    return dict(value)


def validate_evidence(items: object) -> tuple[dict, ...]:
    if not isinstance(items, list) or len(items) > MAX_EVIDENCE_ITEMS:
        raise SoulEvidenceError("invalid evidence collection")
    out = tuple(_validate_item(item) for item in items)
    ids = [item["evidence_id"] for item in out]
    if len(set(ids)) != len(ids):
        raise SoulEvidenceError("duplicate evidence_id")
    return out


def _decision_public(decision: SoulDecision) -> dict:
    return {
        "selected_action_id": decision.selected_action_id,
        "soul_a": {
            "confidence": decision.soul_a.confidence,
            "candidate_actions": list(decision.soul_a.candidate_actions),
        },
        "soul_b": {
            "confidence": decision.soul_b.confidence,
            "blocked_actions": list(decision.soul_b.blocked_actions),
        },
        "soul_c": {
            "confidence": decision.soul_c.confidence,
            "selected_action_id": decision.soul_c.selected_action_id,
        },
    }


def _result(
    decision: SoulDecision, evidence: tuple[dict, ...], outcome: str, reason: str, candidate: str
) -> SoulGateResult:
    return SoulGateResult(
        requested_action_id=decision.selected_action_id,
        governed_candidate_id=candidate,
        outcome=outcome,
        reason=reason,
        decision_sha256=hashlib.sha256(_canonical(_decision_public(decision))).hexdigest(),
        evidence_sha256=hashlib.sha256(_canonical(list(evidence))).hexdigest(),
    )


def gate_soul_decision(decision: SoulDecision, evidence_items: object) -> SoulGateResult:
    evidence = validate_evidence(evidence_items)
    selected = decision.selected_action_id
    if selected == "A05_NO_ACTION":
        return _result(decision, evidence, "NO_ACTION", "NO_ACTION_SELECTED", "A05_NO_ACTION")
    if selected in decision.soul_b.blocked_actions:
        return _result(decision, evidence, "SAFE_FALLBACK", "CRITIC_BLOCK", "A05_NO_ACTION")

    fresh_support = False
    fresh_contradiction = False
    for item in evidence:
        if selected not in item["actions"] or item["freshness"] != "FRESH":
            continue
        if item["stance"] == "SUPPORT":
            fresh_support = True
        elif item["stance"] == "CONTRADICT":
            fresh_contradiction = True

    if fresh_contradiction:
        return _result(decision, evidence, "SAFE_FALLBACK", "FRESH_CONTRADICTION", "A05_NO_ACTION")
    if not fresh_support:
        return _result(decision, evidence, "SAFE_FALLBACK", "NO_FRESH_SUPPORT", "A05_NO_ACTION")
    return _result(decision, evidence, "APPROVE_CANDIDATE", "EVIDENCE_GATE_PASS", selected)


def soul_audit_summary(result: SoulGateResult) -> str:
    if not isinstance(result, SoulGateResult):
        raise SoulEvidenceError("invalid soul gate result")
    return json.dumps(
        {
            "requested_action_id": result.requested_action_id,
            "governed_candidate_id": result.governed_candidate_id,
            "outcome": result.outcome,
            "reason": result.reason,
            "decision_sha256": result.decision_sha256,
            "evidence_sha256": result.evidence_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def append_soul_audit(path: str, event_id: str, result: SoulGateResult) -> dict:
    return append_event(
        path,
        event_id=event_id,
        kind="SYSTEM",
        subject="soul_gate",
        summary=soul_audit_summary(result),
    )
