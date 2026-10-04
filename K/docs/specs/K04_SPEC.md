# K04 — Model Interface / Deliberation Contract

Status: PASS
Purpose: make the reasoning model replaceable while treating every model response as hostile/untrusted data.

## Scope
- provider-independent callable interface;
- exactly one provider call per K04 invocation; no implicit retry/fallback;
- bounded prompt;
- strict deliberation JSON: schema, assessment, confidence, candidate_actions only;
- candidate actions must come from the K01 registry; no params/process specs;
- assessment is bounded non-executable text and never grants authority.

## Non-goals
No chain-of-thought persistence, no provider credentials, no model self-selection, no model-driven tool discovery, no automatic fallback cascade.

## PASS gate
- duplicate/extra/trailing/malformed/oversize model output rejected;
- invalid confidence/action/list/type rejected;
- provider exception produces controlled error and no retry;
- exact one-call behavior verified;
- free-form assessment cannot create an action outside candidate_actions;
- targeted/adversarial + repeat + K00-K04 regression + compile PASS;
- real F remains untouched.