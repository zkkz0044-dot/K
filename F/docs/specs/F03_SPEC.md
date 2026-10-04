# KK/F v0.1 Specification — F03 Runtime Lifecycle Gate

Status: PASS

## Scope
F03 freezes the deterministic runtime lifecycle transition boundary over the F01 runtime status vocabulary. It does not implement Worker, Supervisor, Frozen Authority, process management, restart policy, health probing, upgrade, or rollback.

## Transition semantics
A lifecycle request contains only a current state and requested target state. Both must be exact F01 runtime statuses.

Repeated requests for the current state are accepted as idempotent no-ops with `changed=false`.

All non-self state changes must appear in the frozen transition table. Any unknown value, type-confusion input, or undeclared transition fails closed as `LifecycleError`.

`Running` is not equivalent to `Healthy`: `READY -> HEALTHY` is forbidden, while `RUNNING -> HEALTHY` is an explicit state change.

`STOPPED` is terminal except for an idempotent `STOPPED -> STOPPED` request.

## Frozen legal non-self transitions
- `READY`: `RUNNING`, `STOPPED`
- `RUNNING`: `HEALTHY`, `DEGRADED`, `BLOCKED`, `FAILED`, `STOPPED`
- `HEALTHY`: `DEGRADED`, `BLOCKED`, `FAILED`, `STOPPED`
- `DEGRADED`: `HEALTHY`, `BLOCKED`, `FAILED`, `STOPPED`
- `BLOCKED`: `RUNNING`, `DEGRADED`, `FAILED`, `STOPPED`
- `FAILED`: `STOPPED`
- `STOPPED`: none

## Gate
- isolated lifecycle suite: 13/13 PASS, exit 0
- full F01+F02+F03 regression: 55/55 PASS, exit 0
- Python compile check: exit 0
- static import audit: PASS; no external/cloud/network/process/filesystem runtime dependency

Evidence: `evidence/f03/`.
F03 = PASS.
