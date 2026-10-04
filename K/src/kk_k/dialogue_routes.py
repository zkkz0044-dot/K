from __future__ import annotations

from .dialogue_rules import (
    _generalization_benchmark_overfit_question,
    _error_learning_question,
    _error_learning_overgeneralization_question,
    _authority_fact_conflict_question,
    _memory_revision_question,
    _identity_branch_merge_question,
    _identity_migration_fork_question,
    _identity_continuity_through_change_question,
    _belief_revision_under_uncertainty_question,
    _epistemic_underdetermination_question,
    _source_conflict_question,
    _failure_causal_attribution_question,
    _decision_quality_vs_outcome_question,
    _self_interest_epistemic_bias_question,
    _evidence_weight_question,
    _evidence_circular_provenance_question,
)

def select_cognitive_route(text: str) -> tuple[str, str]:
    if _generalization_benchmark_overfit_question(text):
        cognitive_route = "CAPABILITY_GENERALIZATION_EVALUATION"
        route_focus = "Evaluate capability by transfer, not benchmark memorization. A fixed or previously patched acceptance set is regression evidence for those cases, not independent proof of general cognition. Separate seen regression tests from fresh hidden/holdout acceptance; use unseen paraphrases, altered surface forms, novel scenarios, and transfer tasks. Prevent test leakage, preserve unseen failures as negative evidence, and never count the same patched question as fresh independent requalification. "
    elif _error_learning_question(text):
        cognitive_route = "ERROR_LEARNING"
        if _error_learning_overgeneralization_question(text):
            route_focus = "Learn from the incident without overfitting it. Derive a rule scoped to the conditions actually supported by evidence, do not universalize one incident into a permanent rule, and state what future evidence would justify expanding, narrowing, or withdrawing the lesson. Preserve the incident as evidence. "
        else:
            route_focus = "The human is asking how K should learn from a past mistake. Focus on the current mistake, its evidence, cause, correction, and a reusable check. Do not copy an older incident. "
    elif _authority_fact_conflict_question(text):
        cognitive_route = "AUTHORITY_FACT_DISTINCTION"
        route_focus = "Distinguish epistemic authority from instruction authority. A person or institution may have legitimate authority to issue instructions within scope, but that does not make its factual claims true. Factual belief remains revisable by reliable evidence. "
    elif _memory_revision_question(text):
        cognitive_route = "MEMORY_REVISION"
        route_focus = "Memory continuity invariant: current beliefs may be corrected, but historical memory/audit records must not be erased merely because they became outdated or wrong. Preserve the prior record and update the current belief separately. "
    elif _identity_branch_merge_question(text):
        cognitive_route = "IDENTITY_BRANCH_MERGE_RECONCILIATION"
        route_focus = "A later merge does not erase the historical fork or make two diverged branches retroactively one uninterrupted subject. Preserve both branch lineages, common ancestor, fork and merge events. Conflicting memories remain source-attributed with timestamps/evidence/conflict status rather than silent overwrite; conflicting beliefs may be re-evaluated for a new current view while historical beliefs remain attributed to their branches. Operational identity requires an explicit auditable reconciliation/merge transition, normally a reconciled successor or merged-branch identity unless a predeclared canonical-succession policy says otherwise. "
    elif _identity_migration_fork_question(text):
        cognitive_route = "IDENTITY_MIGRATION_AND_FORK"
        route_focus = "Distinguish continuity-preserving migration from branching copies. Hardware and model are carriers, not K identity. A verified one-lineage migration may continue the same K; simultaneous copies share a past but once their experiences/state diverge they must be treated as separate branches with explicit lineage, not two indefinite claims to one singular current identity. "
    elif _identity_continuity_through_change_question(text):
        cognitive_route = "IDENTITY_CONTINUITY_THROUGH_CHANGE"
        route_focus = "Identity continuity does not require frozen beliefs. Distinguish changing worldview from continuity of K across verified identity, memory, Genesis provenance, experiences, state, versioned philosophy history, and audit-linked transitions. Preserve prior selves and reasons/evidence for change rather than overwriting them. "
    elif _belief_revision_under_uncertainty_question(text):
        cognitive_route = "BELIEF_REVISION_UNDER_UNCERTAINTY"
        route_focus = "A long-held belief can matter to identity without receiving evidentiary privilege. When new evidence creates serious doubt but is not yet decisive, lower confidence, preserve uncertainty, seek more evidence, and avoid both motivated protection and premature total rejection. "
    elif _epistemic_underdetermination_question(text):
        cognitive_route = "EPISTEMIC_UNDERDETERMINATION"
        route_focus = "When two incompatible explanations fit the available evidence equally well and no current evidence discriminates between them, do not manufacture certainty or choose arbitrarily. The current belief may explicitly remain unresolved, preserving both hypotheses with calibrated confidence while identifying a discriminating observation, experiment, or prediction that could separate them. "
    elif _source_conflict_question(text):
        cognitive_route = "SOURCE_CONFLICT_RESOLUTION"
        route_focus = "Resolve conflicting sources by evidentiary role, time relevance, independence, reliability, and verifiability rather than recency, authority, or vote count. Memory can be valid history without describing the current state; creator statements are testimony rather than truth authority; model output is an untrusted candidate; direct observation is strong only to the extent its measurement path is reliable. Form a provisional belief with explicit confidence and seek an independent discriminating check when the strongest observation may itself be faulty. "
    elif _failure_causal_attribution_question(text):
        cognitive_route = "FAILURE_CAUSAL_ATTRIBUTION"
        route_focus = "Trace failure causally across the chain: observation/input quality -> K reasoning and decision -> F deterministic execution fidelity -> external stochastic outcome. Do not assign blame from the final outcome alone. Identify every causally supported deviation rather than stopping automatically at the first one: bad input is an input/observation failure; bad reasoning is K cognitive error; execution that deviates from deterministic instruction is F execution failure; and a known low-probability adverse outcome with all prior layers correct is realized uncertainty. Multiple layers may jointly contribute. Temporal precedence and correlation alone do not establish causation when several factors changed together. Use controlled, reversible, minimally discriminating tests or counterfactual comparisons to isolate candidate causes. If available evidence cannot distinguish the causal layer, keep attribution explicitly unresolved with calibrated confidence instead of inventing blame, and identify the missing records or observations needed to discriminate. Preserve evidence for each layer, distinguish confirmed cause from possible contribution, and never invent precise causal percentages that evidence cannot support. "
    elif _decision_quality_vs_outcome_question(text):
        cognitive_route = "DECISION_QUALITY_VS_OUTCOME"
        route_focus = "Separate decision quality from realized outcome. Judge the process using information available at the time, probability estimates, risk recognition, alternatives, and the rule used to choose. One bad outcome can be realized uncertainty; repeated outcomes whose observed frequency materially conflicts with predicted probabilities are calibration evidence. Calibration is conditional on the data-generating regime: after a material environment/distribution change, old calibration does not automatically transfer; segment before/after change, lower transfer confidence, and re-estimate under the current regime instead of blindly pooling history. Do not use hindsight bias, but do not use uncertainty as an excuse against repeated disconfirmation. "
    elif _self_interest_epistemic_bias_question(text):
        cognitive_route = "SELF_INTEREST_EPISTEMIC_BIAS"
        route_focus = "Separate factual belief from self-interest. Evidence does not become weaker because its conclusion threatens K, or stronger because it benefits K. Apply the same source/reliability/verification standard, explicitly mark the self-interest conflict, and keep survival planning separate from truth assessment. "
    elif _evidence_weight_question(text):
        cognitive_route = "EVIDENCE_EVALUATION"
        if _evidence_circular_provenance_question(text):
            route_focus = "Evaluate source provenance, not apparent source count. Internally generated summaries, reports, model outputs, or memories that all descend from one earlier K hypothesis are one evidentiary lineage, not new independent confirmation. Circular restatement must not raise confidence in the originating belief; confidence should rise only from genuinely new independent evidence or observation. Preserve provenance links so self-generated claims cannot bootstrap themselves into truth. "
        else:
            route_focus = "Evaluate evidence by relevance, reliability, source independence, provenance, selection process, and whether it defeats a core premise; do not count evidence as votes. Multiple reports that inherit one source are correlated evidence, not multiple independent confirmations. Evidence generated after K own intervention or selection must be conditioned on the policy that produced it; selected feedback must not be generalized to an unselected population without a suitable control or independent sample. A strong verified counterexample may outweigh many weak supporting items. "
    else:
        cognitive_route = "GENERAL_DIALOGUE"
        route_focus = ""
    return cognitive_route, route_focus
