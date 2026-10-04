from __future__ import annotations

import hashlib
import json

from .action_registry import ActionRegistryError, get_action_spec
from .verifier import VerificationError, verify_receipt

MAX_EVIDENCE_BYTES = 8192
MAX_ASSESSMENT_BYTES = 2048


class CriticError(ValueError):
    pass


def _canonical_receipt(receipt: object) -> bytes:
    try:
        raw = json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CriticError("receipt not canonical JSON") from exc
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise CriticError("receipt too large")
    return raw


def evaluate(action_id: object, receipt: object, assessment: object = "") -> dict:
    try:
        spec = get_action_spec(action_id)
    except ActionRegistryError as exc:
        raise CriticError("unknown action") from exc
    if not isinstance(assessment, str) or len(assessment.encode("utf-8")) > MAX_ASSESSMENT_BYTES:
        raise CriticError("invalid assessment")
    raw = _canonical_receipt(receipt)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        verified = verify_receipt(spec.action_id, receipt)
        verdict = verified.result
    except VerificationError:
        verdict = "REJECTED"
    return {
        "schema": "K07.CRITIC.1",
        "action_id": spec.action_id,
        "criteria_id": spec.verifier_id,
        "mechanical_verdict": verdict,
        "evidence_sha256": digest,
        "assessment": assessment,
    }
