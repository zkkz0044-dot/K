# KK/F v0.1 Specification — F19 Frozen-Authority Runtime Bootstrap

Status: PASS

## Scope
F19 composes F18 Frozen Authority, F08 restart ledger initialization, and F13 managed process launch into a safe initial worker bootstrap.

## Semantics
- Frozen Authority authorization occurs before any runtime state creation
- restart budget is sourced only from the authorized manifest
- durable restart ledger is initialized before worker launch
- worker launch still performs F10 integrity preflight through F13
- initial worker status is RUNNING only; bootstrap never claims HEALTHY
- unauthorized path/digest or mutable authority blocks before ledger creation
- candidate content change after authority declaration is caught by launch preflight; zero-attempt ledger may remain initialized
- existing ledger blocks a second bootstrap rather than silently resetting budget
- no network/cloud/AI/SSH/Bridge runtime dependency

## Gate
- verification-command syntax failure retained as raw failure evidence
- corrected isolated suite: 9/9 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F19 regression: 248/248 PASS, exit 0
- Python compile: exit 0
- static ordering/dependency audit: PASS, exit 0

Evidence: `evidence/f19/`.
F19 = PASS.
