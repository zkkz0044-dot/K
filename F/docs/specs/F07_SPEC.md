# KK/F v0.1 Specification — F07 Bounded Restart Decision Gate

Status: PASS

## Scope
F07 provides a deterministic bounded decision for whether a failed runtime instance may be replaced. It prevents unbounded retry loops. It does not itself stop, start, spawn, kill, supervise, or replace any process and does not read time or external services.

## Decision vocabulary
Exact values:
- `NO_ACTION`
- `REPLACE_INSTANCE`
- `HOLD_FAILED`

## Semantics
- status must be an exact frozen F01 runtime status
- attempts is an integer >= 0; booleans rejected
- max_attempts is an integer >= 1; booleans rejected
- attempts > max_attempts fails closed
- any non-FAILED runtime status => `NO_ACTION`
- FAILED with attempts < max_attempts => `REPLACE_INSTANCE`
- FAILED with attempts == max_attempts => `HOLD_FAILED`
- replacing means a later layer may create a new runtime instance; F07 does not bypass F03 terminal semantics of an existing failed/stopped instance

## Gate
- isolated restart-policy suite: 13/13 PASS, exit 0
- full F01-F07 regression: 115/115 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS

Evidence: `evidence/f07/`.
F07 = PASS.
