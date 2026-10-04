# KK/F v0.1 Specification — F17 Durable Supervision Audit Evidence

Status: PASS

## Scope
F17 converts F16 supervision outcomes into strict F01-valid `result` records and appends them through the accepted F02 tamper-evident evidence chain.

## Semantics
- input must be an F16 HealthSupervisionResult
- record role direction is frozen as supervisor -> operator
- record kind is `result`
- record status is the F16 health status
- payload records process_status, decision, attempts, contained, replacement_pid
- message_id and timestamp remain explicit caller inputs and must satisfy F01
- F02 verifies existing chain before append; corrupt store blocks new evidence
- invalid record input does not mutate evidence store
- no direct file/network/cloud/AI/SSH/Bridge dependency beyond the accepted F02 local evidence primitive

## Gate
- isolated suite: 8/8 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F17 regression: 227/227 PASS, exit 0
- Python compile: exit 0
- static dependency/boundary audit: PASS, exit 0

Evidence: `evidence/f17/`.
F17 = PASS.
