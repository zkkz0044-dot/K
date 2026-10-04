# KK/F v0.1 Specification — F15 Managed Process Health Gate

Status: PASS

## Scope
F15 combines actual F13 managed-process observation with explicit F05 heartbeat freshness evidence. It is the gate that prevents process existence from being mistaken for health.

## Semantics
- current must be an F13 ManagedProcess
- actual process observation is read first
- if the process is not RUNNING, its terminal lifecycle status is authoritative and heartbeat data is not allowed to override it
- only a RUNNING process proceeds to heartbeat freshness evaluation
- RUNNING + fresh heartbeat => HEALTHY
- RUNNING + aged heartbeat => DEGRADED
- RUNNING + stale heartbeat => FAILED
- malformed/future heartbeat or invalid thresholds fail closed while process is RUNNING
- no host clock is read; `now` remains an explicit input
- no network/cloud/AI/SSH/Bridge runtime dependency

## Gate
- isolated suite: 9/9 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F15 regression: 211/211 PASS, exit 0
- Python compile: exit 0
- static dependency/clock audit: PASS, exit 0

Evidence: `evidence/f15/`.
F15 = PASS.
