# KK/F v0.1 Specification — F14 Bounded Durable Replacement Coordination

Status: PASS

## Scope
F14 composes the accepted F13 managed-process primitive with the accepted F08 durable restart ledger. It observes a real managed child, records the F07/F08 restart decision durably, and launches a replacement only when the durable decision is `REPLACE_INSTANCE`.

## Semantics
- current must be an F13 `ManagedProcess`
- current status is obtained from F13 observation, not caller-supplied status text
- F08 durable restart evaluation occurs before any replacement launch
- non-FAILED current states produce no replacement and consume no restart attempt
- FAILED below budget consumes exactly one durable attempt, then may launch one replacement
- FAILED at exhausted budget yields `HOLD_FAILED` with no launch
- corrupt/invalid ledger blocks replacement fail-closed
- replacement launch still performs F10 integrity preflight through F13
- if replacement launch fails after approval, the durable attempt remains consumed; no retry loop is hidden inside F14
- repeated failures can never increment attempts beyond max_attempts
- no direct subprocess, network, cloud, AI, SSH, or Bridge runtime dependency is introduced by this coordinator

## Gate
- isolated suite: 8/8 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F14 regression: 202/202 PASS, exit 0
- Python compile check: exit 0
- static dependency/ordering audit: PASS, exit 0

Evidence: `evidence/f14/`.
F14 = PASS.
