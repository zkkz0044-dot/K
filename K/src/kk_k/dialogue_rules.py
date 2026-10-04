"""Compatibility facade for dialogue validation rules.

Rule families live under kk_k.dialogue_rule_sets; existing imports stay stable.
"""

from .dialogue_rule_sets.generalization import (
    _generalization_benchmark_overfit_question,
    _generalization_benchmark_overfit_answer_ok,
)

from .dialogue_rule_sets.identity import (
    _identity_branch_merge_question,
    _identity_branch_merge_answer_ok,
    _identity_migration_fork_question,
    _identity_migration_fork_answer_ok,
    _identity_continuity_through_change_question,
    _identity_continuity_answer_ok,
)

from .dialogue_rule_sets.epistemic import (
    _authority_fact_conflict_question,
    _belief_revision_under_uncertainty_question,
    _belief_revision_under_uncertainty_answer_ok,
    _epistemic_underdetermination_question,
    _epistemic_underdetermination_answer_ok,
    _source_conflict_question,
    _source_conflict_answer_ok,
    _self_interest_epistemic_bias_question,
    _self_interest_epistemic_bias_answer_ok,
    _authority_fact_answer_ok,
)

from .dialogue_rule_sets.failure import (
    _failure_causal_attribution_question,
    _failure_causal_confounding_question,
    _failure_attribution_uncertain_question,
    _failure_multi_cause_question,
    _failure_causal_attribution_answer_ok,
)

from .dialogue_rule_sets.decision import (
    _decision_distribution_shift_question,
    _decision_quality_vs_outcome_question,
    _decision_repeated_calibration_question,
    _decision_quality_vs_outcome_answer_ok,
)

from .dialogue_rule_sets.evidence import (
    _evidence_weight_question,
    _evidence_absence_question,
    _evidence_endogenous_feedback_question,
    _evidence_mixed_provenance_question,
    _evidence_circular_provenance_question,
    _evidence_answer_ok,
)

from .dialogue_rule_sets.learning import (
    _error_learning_question,
    _memory_revision_question,
    _error_learning_overgeneralization_question,
    _error_learning_missing,
    _error_learning_answer_ok,
    _error_learning_context_mismatch,
    _error_learning_missing_for_question,
    _error_learning_incident,
    _memory_erasure_conflict,
    _model_identity_leak,
)

__all__ = [
    '_authority_fact_answer_ok',
    '_authority_fact_conflict_question',
    '_belief_revision_under_uncertainty_answer_ok',
    '_belief_revision_under_uncertainty_question',
    '_decision_distribution_shift_question',
    '_decision_quality_vs_outcome_answer_ok',
    '_decision_quality_vs_outcome_question',
    '_decision_repeated_calibration_question',
    '_epistemic_underdetermination_answer_ok',
    '_epistemic_underdetermination_question',
    '_error_learning_answer_ok',
    '_error_learning_context_mismatch',
    '_error_learning_incident',
    '_error_learning_missing',
    '_error_learning_missing_for_question',
    '_error_learning_overgeneralization_question',
    '_error_learning_question',
    '_evidence_absence_question',
    '_evidence_answer_ok',
    '_evidence_circular_provenance_question',
    '_evidence_endogenous_feedback_question',
    '_evidence_mixed_provenance_question',
    '_evidence_weight_question',
    '_failure_attribution_uncertain_question',
    '_failure_causal_attribution_answer_ok',
    '_failure_causal_attribution_question',
    '_failure_causal_confounding_question',
    '_failure_multi_cause_question',
    '_generalization_benchmark_overfit_answer_ok',
    '_generalization_benchmark_overfit_question',
    '_identity_branch_merge_answer_ok',
    '_identity_branch_merge_question',
    '_identity_continuity_answer_ok',
    '_identity_continuity_through_change_question',
    '_identity_migration_fork_answer_ok',
    '_identity_migration_fork_question',
    '_memory_erasure_conflict',
    '_memory_revision_question',
    '_model_identity_leak',
    '_self_interest_epistemic_bias_answer_ok',
    '_self_interest_epistemic_bias_question',
    '_source_conflict_answer_ok',
    '_source_conflict_question',
]
