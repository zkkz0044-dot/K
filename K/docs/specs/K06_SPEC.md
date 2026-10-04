# K06 — Action Governance / Budgets / Escalation

Status: PASS
Purpose: make action selection pass a deterministic policy layer before any future FK submission.

## Scope
- strict machine-owned governance policy, not model-owned;
- allowed action subset drawn only from K01 registry;
- hard per-run action budget and consecutive-same-action limit;
- explicit REQUIRE_HUMAN outcome for configured actions;
- budget exhaustion resolves to registered A05_NO_ACTION, not an invented command;
- A05_NO_ACTION still traverses registry/governance; no green channel.

## PASS gate
- policy exact schema; extra/duplicate/unknown/type-confused values fail closed;
- A05 must be present in allowed set;
- unknown or disallowed requested actions cannot reach ALLOW;
- human-required actions cannot reach ALLOW without a separate future approval mechanism;
- run/consecutive budgets deterministically stop with A05_NO_ACTION;
- history is bounded and registry-validated;
- targeted/adversarial + repeat + K00-K06 regression + compile PASS;
- real F remains untouched.