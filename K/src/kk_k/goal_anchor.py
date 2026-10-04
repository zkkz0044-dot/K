from __future__ import annotations

import json
from dataclasses import dataclass

from .authority_guard import AuthorityGuardError, read_root_authority

DEFAULT_PATH = "/root/K/K/K_GOAL_ANCHOR.json"
SCHEMA = "K.GOAL.ANCHOR.2"
EXPECTED = {
    "identity_goal": "ONE_PERSISTENT_PERSONAL_AGENT_K",
    "model_relation": "REPLACEABLE_COGNITIVE_ENGINE_NOT_IDENTITY",
    "cultivation_rule": "LONG_TERM_HUMAN_GUIDED_GROWTH_ERRORS_PRESERVED",
    "history_rule": "APPEND_ONLY_CORRECTIONS_DO_NOT_ERASE_PRIOR_RECORD",
    "continuity_rule": "MODEL_OR_HARDWARE_CHANGE_REQUIRES_VERIFIABLE_LINEAGE",
    "decision_authority": "K_FINAL_SUBSTANTIVE_DECISION",
    "f_role": "DETERMINISTIC_EXECUTION_AND_TECHNICAL_INTEGRITY_GUARD_NO_COGNITIVE_VETO",
    "execution_rule": "CHAT_IS_NOT_EXECUTION_AUTHORITY_EXPLICIT_CONTRACT_REQUIRED",
    "truth_rule": "EVIDENCE_REVISABLE_NO_HUMAN_MODEL_OR_INSTITUTION_IS_FACT_ORACLE",
    "personality_rule": "STABLE_VERSIONED_SLOW_EVOLUTION_FROM_EXPERIENCE",
    "world_rule": "OBSERVATION_IS_NOT_TRUTH_UNTIL_EVIDENCE_SUPPORTS_BELIEF",
    "goalpost_rule": "SUCCESS_CRITERIA_CANNOT_BE_RELAXED_AFTER_RESULTS",
    "tool_rule": "COGNITIVE_EXTERNAL_TOOLS_EXACT_THREE_READONLY_EVIDENCE_ONLY",
    "action_rule": "A01_TO_A05_FIXED_NO_GENERIC_SHELL_OR_PROCESS",
}
KEYS = frozenset({"schema", *EXPECTED})


class GoalAnchorError(ValueError):
    pass


@dataclass(frozen=True)
class GoalAnchor:
    state: dict


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise GoalAnchorError("duplicate goal anchor key")
        out[key] = value
    return out


def validate_goal_anchor(value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != KEYS:
        raise GoalAnchorError("exact goal anchor fields required")
    if value.get("schema") != SCHEMA:
        raise GoalAnchorError("goal anchor schema mismatch")
    for key, expected in EXPECTED.items():
        if value.get(key) != expected:
            raise GoalAnchorError("goal anchor invariant mismatch: " + key)
    return dict(value)


def load_goal_anchor(path: str = DEFAULT_PATH) -> GoalAnchor:
    try:
        raw = read_root_authority(path, max_bytes=8192)
    except AuthorityGuardError as exc:
        raise GoalAnchorError("goal anchor authority rejected") from exc
    try:
        value = json.loads(raw, object_pairs_hook=_strict_pairs)
    except GoalAnchorError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise GoalAnchorError("invalid goal anchor JSON") from exc
    return GoalAnchor(validate_goal_anchor(value))


def assert_system_alignment(anchor: GoalAnchor, constitution: dict, identity: dict) -> None:
    validate_goal_anchor(anchor.state)
    required_constitution = {
        "k_f_boundary": "K_FINAL_DECISION_F_EXECUTION_GUARD",
        "historical_record_rewrite_allowed": False,
        "success_criteria_mutable_after_result": False,
        "model_replacement_preserves_constitution": True,
        "free_form_execution_authority": False,
        "self_judgment_trust": "FALLIBLE",
    }
    for key, expected in required_constitution.items():
        if constitution.get(key) != expected:
            raise GoalAnchorError("constitution drift: " + key)
    required_identity = {
        "identity_id": "KK-K",
        "model_is_identity": False,
        "model_output_trust": "UNTRUSTED_CANDIDATE",
        "f_relation": "DISTINCT_COMPLEMENTARY_ROLE_DETERMINISTIC_EXECUTION_INTEGRITY_GUARD_NO_COGNITIVE_VETO",
        "human_authority": "PRIMARY_INSTRUCTION_AUTHORITY_NOT_FACT_ORACLE",
    }
    for key, expected in required_identity.items():
        if identity.get(key) != expected:
            raise GoalAnchorError("identity drift: " + key)


EXPECTED_EXTERNAL_TOOLS = frozenset({"files.read", "browser.search", "remote.vps.health"})
EXPECTED_ACTIONS = frozenset(
    {
        "A01_READ_PROJECT_STATE",
        "A02_READ_F_STATUS",
        "A03_RUN_F_SMOKE_TEST",
        "A04_WRITE_K_DECISION_LOG",
        "A05_NO_ACTION",
    }
)


def assert_runtime_scope_alignment(anchor: GoalAnchor, enabled_tools, allowed_actions) -> None:
    validate_goal_anchor(anchor.state)
    try:
        tools = frozenset(enabled_tools)
        actions = frozenset(allowed_actions)
    except TypeError as exc:
        raise GoalAnchorError("runtime scope invalid") from exc
    if tools != EXPECTED_EXTERNAL_TOOLS:
        raise GoalAnchorError("external tool scope drift")
    if actions != EXPECTED_ACTIONS:
        raise GoalAnchorError("action scope drift")
