# KK/F v0.1 Specification — F06 Monotonic Heartbeat Stream Gate

Status: PASS

## Scope
F06 accepts a heartbeat only when it advances a previously accepted heartbeat monotonically. It prevents sequence replay and timestamp rollback. It does not evaluate freshness, read the host clock, persist stream state, supervise processes, restart components, or contact external services.

## Semantics
Both previous and current heartbeat records must satisfy the F05 heartbeat schema.

- `previous=None` permits the first valid heartbeat
- current sequence must strictly exceed previous sequence
- current observed_at must represent an instant strictly later than previous observed_at
- sequence jumps are allowed; only strict monotonicity is required
- timezone-equivalent timestamps are treated as the same instant and rejected as non-advancing
- fractional-second advancement is accepted
- invalid previous/current heartbeat input fails closed as `HeartbeatStreamError`
- F06 deliberately does not decide whether a timestamp is too far in the future; freshness authority remains F05 with explicit `now`

## Gate
- isolated stream suite: 14/14 PASS, exit 0
- full F01-F06 regression: 102/102 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS

Evidence: `evidence/f06/`.
F06 = PASS.
