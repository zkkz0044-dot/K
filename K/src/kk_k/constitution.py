from __future__ import annotations

import json

from .authority_guard import AuthorityGuardError, read_root_authority

CONSTITUTION_KEYS = frozenset(
    {
        "schema",
        "k_f_boundary",
        "llm_output_trust",
        "unknown_fields",
        "unknown_actions",
        "success_criteria_mutable_after_result",
        "no_action_legitimate",
        "action_green_channel",
        "free_form_execution_authority",
        "historical_record_rewrite_allowed",
        "truth_seeking_priority",
        "model_replacement_preserves_constitution",
        "trust_root_mode",
        "trusted_roots",
        "external_inputs_default_trust",
        "self_judgment_trust",
        "soul_outputs_trust",
        "project_root",
        "filesystem_scope",
        "cross_project_access",
        "webroot_staging",
        "temporary_http_transfer",
        "external_storage_staging",
        "fk_access_before_user_approval",
        "runtime_authority_mirror",
        "runtime_authority_mirror_requires_readonly_mount",
    }
)
EXPECTED = {
    "schema": "K00.CONSTITUTION.1",
    "k_f_boundary": "K_FINAL_DECISION_F_EXECUTION_GUARD",
    "llm_output_trust": "UNTRUSTED",
    "unknown_fields": "REJECT",
    "unknown_actions": "REJECT",
    "success_criteria_mutable_after_result": False,
    "no_action_legitimate": True,
    "action_green_channel": False,
    "free_form_execution_authority": False,
    "historical_record_rewrite_allowed": False,
    "truth_seeking_priority": True,
    "model_replacement_preserves_constitution": True,
    "trust_root_mode": "SELF_AND_F_ONLY",
    "trusted_roots": ["K_INTEGRITY_VERIFIED_CORE", "F"],
    "external_inputs_default_trust": "UNTRUSTED_EVIDENCE",
    "self_judgment_trust": "FALLIBLE",
    "soul_outputs_trust": "UNTRUSTED_CANDIDATE",
    "project_root": "/root/K/K",
    "filesystem_scope": "PROJECT_ROOT_ONLY",
    "cross_project_access": False,
    "webroot_staging": False,
    "temporary_http_transfer": False,
    "external_storage_staging": False,
    "fk_access_before_user_approval": False,
    "runtime_authority_mirror": "/run/kk-k-ro",
    "runtime_authority_mirror_requires_readonly_mount": True,
}


class ConstitutionError(ValueError):
    pass


def _strict_json(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ConstitutionError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except ConstitutionError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConstitutionError("invalid constitution JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != CONSTITUTION_KEYS:
        raise ConstitutionError("exact constitution fields required")
    return value


def validate_constitution(value: dict) -> dict:
    for key, expected in EXPECTED.items():
        if value.get(key) != expected or type(value.get(key)) is not type(expected):
            raise ConstitutionError(f"constitutional invariant mismatch: {key}")
    return dict(value)


def load_constitution(path: str) -> dict:
    try:
        raw = read_root_authority(path, max_bytes=16384)
    except AuthorityGuardError as exc:
        raise ConstitutionError("constitution authority rejected") from exc
    return validate_constitution(_strict_json(raw))
