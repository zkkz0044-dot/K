# KK/F v0.1 Specification — F20 Integrated Authorized Audited Runtime Cycle

Status: PASS

## Scope
F20 closes the local F runtime path by composing Frozen Authority authorization, restart-ledger consistency, monotonic heartbeat acceptance, health supervision/containment/replacement, and durable F02 audit evidence in one ordered cycle.

## Semantics
- Frozen Authority authorization is rechecked first for the replacement candidate
- durable ledger max_attempts must exactly match Frozen Authority max_restart_attempts
- F06 monotonic heartbeat stream gate runs before health action
- replay/regressed heartbeat fails closed before action/evidence
- F16 performs health classification, containment, durable restart accounting, and bounded replacement
- F17 records each successful supervision outcome into F02 evidence
- evidence-commit failure after replacement attempts to stop the newly launched replacement and fails closed
- next current worker is replacement when one is created; contained/failed-without-replacement yields no current worker
- explicit timestamps only; no host-clock dependency in F20
- no GitHub/cloud drive/ChatGPT/Codex/Supabase/SSH/Bridge runtime dependency

## Gate
- isolated integrated suite: 9/9 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F20 regression: 257/257 PASS, exit 0
- Python compile: exit 0
- static integration-order/dependency audit: PASS, exit 0
- final end-to-end minimal-environment run: PASS, exit 0
- final end-to-end isolated network namespace run: PASS, exit 0
- final scenario: healthy cycle, two approved replacements, third failed cycle HOLD_FAILED at budget 2, four-record F02 evidence chain verified

Evidence: `evidence/f20/`, `evidence/final/`.
F20 = PASS.
