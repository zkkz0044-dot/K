# KK/F v0.1 Specification — F16 Health-Failure Containment and Replacement

Status: PASS

## Scope
F16 turns F15 health evidence into bounded local containment/replacement action. HEALTHY and DEGRADED processes are left running. FAILED health triggers containment when the child is still RUNNING, then durable F08 restart accounting, then at most one F13 replacement launch when approved.

## Semantics
- F15 establishes health before action
- HEALTHY/DEGRADED produce NO_ACTION and do not mutate restart ledger
- stale-heartbeat FAILED while process is RUNNING is contained via bounded F13 stop before restart accounting
- already-crashed FAILED process does not require containment
- invalid heartbeat or invalid grace fails closed before restart budget mutation
- durable FAILED evaluation occurs before any replacement launch
- exhausted budget yields HOLD_FAILED and no replacement
- replacement integrity/preflight failure after approval leaves the attempt consumed
- no hidden retry loop
- no external/cloud/AI/SSH/Bridge runtime dependency

## Gate
- first test attempt retained: framework helper-name collision, exit 1
- corrected isolated suite: 8/8 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F16 regression: 219/219 PASS, exit 0
- Python compile: exit 0
- static ordering/dependency audit: PASS, exit 0

Evidence: `evidence/f16/`.
F16 = PASS.
