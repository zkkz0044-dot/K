from __future__ import annotations

import json

from ..k_audit_witness import KAuditWitnessError

def _canonical_obj(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KAuditWitnessError("COGNITIVE_STATE_INVALID") from exc
