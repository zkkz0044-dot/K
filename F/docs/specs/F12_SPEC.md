# KK/F v0.1 Specification — F12 Execution Outcome Lifecycle Gate

Status: PASS

## Scope
F12 maps an observed process execution outcome to the frozen F01 lifecycle vocabulary. It is a pure deterministic classifier and does not inspect processes, read clocks/files, restart anything, or contact external services.

## Semantics
- `timed_out` must be an actual boolean
- `exit_code` must be an integer or null; boolean exit codes are rejected
- timed_out=true requires a concrete reaped exit code
- no exit code and no timeout => `RUNNING`
- exit code 0 => `STOPPED`, never `HEALTHY`
- any non-zero exit, including signal-style negative codes => `FAILED`
- any timeout after reap => `FAILED`
- resulting value must belong to the frozen F01 runtime vocabulary

## Boundary
Process existence or exit code does not prove health. HEALTHY remains available only to evidence/heartbeat gates that actually establish it.

## Gate
- isolated execution-status suite: 10/10 PASS, exit 0
- full F01-F12 regression: 182/182 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS

Evidence: `evidence/f12/`.
F12 = PASS.
