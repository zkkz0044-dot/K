# KK/F v0.1 Specification — F08 Durable Restart Budget Ledger

Status: PASS

## Scope
F08 makes F07 restart-budget accounting durable across process restarts by storing the ledger through the verified F04 local checkpoint mechanism. It does not start, stop, spawn, kill, supervise, or replace processes and does not contact external services.

## Ledger payload
Exact fields: `ledger_version`, `attempts`, `max_attempts`, `last_decision`.

- ledger_version is frozen at `0.1`
- attempts is an integer >= 0
- max_attempts is an integer >= 1
- attempts may never exceed max_attempts
- last_decision must be one of the exact F07 decision values
- unknown/missing fields and corrupt F04 checkpoint state fail closed

## Durable semantics
- initialization writes generation 0 with status READY, attempts 0, and NO_ACTION
- every recorded evaluation increments checkpoint generation
- REPLACE_INSTANCE consumes one durable attempt
- NO_ACTION and HOLD_FAILED do not consume budget
- once attempts reaches max_attempts, later FAILED evaluations remain HOLD_FAILED without counter overflow
- invalid runtime status does not mutate the ledger
- failed atomic replacement is wrapped as RestartLedgerError and the previously verified ledger remains readable and unchanged

## Gate
- first isolated run retained as failure evidence: 14 PASS / 1 ERROR, exit 1
- corrected isolated suite: 15/15 PASS, exit 0
- full F01-F08 regression: 130/130 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS
- simulated atomic replace failure preserves previous durable ledger

Evidence: `evidence/f08/`.
F08 = PASS.
