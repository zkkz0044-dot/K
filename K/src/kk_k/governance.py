from __future__ import annotations

import json
from dataclasses import dataclass

from .action_registry import ALLOWED_ACTIONS
from .authority_guard import AuthorityGuardError, read_root_authority

POLICY_KEYS = frozenset(
    {
        "schema",
        "allowed_actions",
        "human_required_actions",
        "max_actions_per_run",
        "max_same_action_consecutive",
    }
)


class GovernanceError(ValueError):
    pass


@dataclass(frozen=True)
class GovernanceDecision:
    outcome: str
    action_id: str
    reason: str


def _strict_json(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise GovernanceError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except GovernanceError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise GovernanceError("invalid policy JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != POLICY_KEYS:
        raise GovernanceError("exact policy fields required")
    return value


def validate_policy(value: dict) -> dict:
    if value["schema"] != "K06.POLICY.1":
        raise GovernanceError("unsupported policy schema")
    allowed = value["allowed_actions"]
    human = value["human_required_actions"]
    if not isinstance(allowed, list) or not allowed or len(allowed) > len(ALLOWED_ACTIONS):
        raise GovernanceError("invalid allowed actions")
    if any(not isinstance(x, str) or x not in ALLOWED_ACTIONS for x in allowed) or len(
        set(allowed)
    ) != len(allowed):
        raise GovernanceError("invalid allowed actions")
    if "A05_NO_ACTION" not in allowed:
        raise GovernanceError("NO_ACTION must remain available")
    if (
        not isinstance(human, list)
        or any(not isinstance(x, str) or x not in allowed for x in human)
        or len(set(human)) != len(human)
    ):
        raise GovernanceError("invalid human-required actions")
    for field, maximum in (("max_actions_per_run", 32), ("max_same_action_consecutive", 8)):
        val = value[field]
        if type(val) is not int or not (1 <= val <= maximum):
            raise GovernanceError(f"invalid {field}")
    return dict(value)


def load_policy(path: str) -> dict:
    try:
        raw = read_root_authority(path, max_bytes=8192)
    except AuthorityGuardError as exc:
        raise GovernanceError("policy authority rejected") from exc
    return validate_policy(_strict_json(raw))


def govern(requested_action: object, policy: dict, history: list[str]) -> GovernanceDecision:
    p = validate_policy(policy)
    if not isinstance(requested_action, str) or requested_action not in ALLOWED_ACTIONS:
        raise GovernanceError("unknown requested action")
    if (
        not isinstance(history, list)
        or len(history) > 32
        or any(not isinstance(x, str) or x not in ALLOWED_ACTIONS for x in history)
    ):
        raise GovernanceError("invalid action history")
    if len(history) >= p["max_actions_per_run"]:
        return GovernanceDecision("STOP", "A05_NO_ACTION", "RUN_BUDGET_EXHAUSTED")
    same = 0
    for action in reversed(history):
        if action != requested_action:
            break
        same += 1
    if same >= p["max_same_action_consecutive"]:
        return GovernanceDecision("STOP", "A05_NO_ACTION", "CONSECUTIVE_BUDGET_EXHAUSTED")
    if requested_action not in p["allowed_actions"]:
        return GovernanceDecision("DENY", "A05_NO_ACTION", "ACTION_NOT_ALLOWED")
    if requested_action in p["human_required_actions"]:
        return GovernanceDecision("REQUIRE_HUMAN", requested_action, "HUMAN_APPROVAL_REQUIRED")
    return GovernanceDecision("ALLOW", requested_action, "POLICY_ALLOW")
