from __future__ import annotations

import json
from dataclasses import dataclass

from .action_registry import ALLOWED_ACTIONS

DECISION_SCHEMA = "K01.DECISION.1"
MAX_DECISION_BYTES = 1024
DECISION_KEYS = frozenset({"schema", "action_id"})


class DecisionError(ValueError):
    pass


@dataclass(frozen=True)
class Decision:
    schema: str
    action_id: str


def _strict_object(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise DecisionError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except DecisionError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise DecisionError("invalid JSON") from exc
    if not isinstance(value, dict):
        raise DecisionError("decision must be an object")
    return value


def parse_decision(raw: object) -> Decision:
    if not isinstance(raw, str):
        raise DecisionError("decision must be UTF-8 text")
    if len(raw.encode("utf-8")) > MAX_DECISION_BYTES:
        raise DecisionError("decision too large")
    value = _strict_object(raw)
    if frozenset(value) != DECISION_KEYS:
        raise DecisionError("exact decision fields required")
    if value["schema"] != DECISION_SCHEMA:
        raise DecisionError("unsupported decision schema")
    action_id = value["action_id"]
    if not isinstance(action_id, str) or action_id not in ALLOWED_ACTIONS:
        raise DecisionError("unknown action_id")
    return Decision(schema=DECISION_SCHEMA, action_id=action_id)
