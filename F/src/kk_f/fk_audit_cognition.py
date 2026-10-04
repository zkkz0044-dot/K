"""Compatibility facade for audit-cognition state helpers.

Implementation is split by domain under kk_f.cognition.
"""
from .cognition.common import _canonical_obj
from .cognition.personality import _one_trait_transition, _personality_state
from .cognition.beliefs import (
    _belief_revision_hash,
    _parse_belief_revision,
    _belief_states,
    _belief_public,
    _query_current_beliefs,
)
from .cognition.skills import (
    _skill_revision_hash,
    _capability_proof,
    _parse_skill_revision,
    _skill_states,
    _skill_public,
    _query_current_skills,
)
