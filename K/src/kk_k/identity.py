from __future__ import annotations
import json
from .authority_guard import AuthorityGuardError, read_root_authority

KEYS = frozenset(
    {
        "schema",
        "identity_id",
        "self_name",
        "role",
        "continuity_basis",
        "model_is_identity",
        "model_output_trust",
        "f_relation",
        "human_authority",
        "soul_roles",
    }
)
EXPECTED = {
    "schema": "K.IDENTITY.1",
    "identity_id": "KK-K",
    "self_name": "K",
    "role": "COGNITIVE_JUDGMENT_LAYER",
    "continuity_basis": "IDENTITY_MEMORY_GENESIS_EXPERIENCE_STATE_HISTORY_AUDIT",
    "model_is_identity": False,
    "model_output_trust": "UNTRUSTED_CANDIDATE",
    "f_relation": "DISTINCT_COMPLEMENTARY_ROLE_DETERMINISTIC_EXECUTION_INTEGRITY_GUARD_NO_COGNITIVE_VETO",
    "human_authority": "PRIMARY_INSTRUCTION_AUTHORITY_NOT_FACT_ORACLE",
    "soul_roles": ["SOUL_A_PROPOSER", "SOUL_B_CRITIC", "SOUL_C_JUDGE"],
}


class IdentityError(ValueError):
    pass


def _strict(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise IdentityError("duplicate identity key")
            out[k] = v
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except IdentityError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise IdentityError("invalid identity JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != KEYS:
        raise IdentityError("exact identity fields required")
    return value


def validate_identity(value: dict) -> dict:
    for k, expected in EXPECTED.items():
        if value.get(k) != expected or type(value.get(k)) is not type(expected):
            raise IdentityError("identity invariant mismatch: " + k)
    return dict(value)


def load_identity(path: str = "/root/K/K/K_IDENTITY.json") -> dict:
    try:
        raw = read_root_authority(path, max_bytes=8192)
    except AuthorityGuardError as exc:
        raise IdentityError("identity authority rejected") from exc
    return validate_identity(_strict(raw))
