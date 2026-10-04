# KK/F v0.1 Specification — F05 Deterministic Heartbeat Freshness Gate

Status: PASS

## Scope
F05 classifies an explicit heartbeat as `HEALTHY`, `DEGRADED`, or `FAILED` from explicit timestamp and threshold inputs. It does not read the host clock, probe processes, restart anything, infer acceptance, schedule work, or contact external services.

## Heartbeat record
Exact fields: `version`, `sequence`, `observed_at`.

- version is frozen at `0.1`
- sequence is an integer >= 0; booleans are rejected
- observed_at is strict timezone-aware RFC3339
- unknown or missing fields fail closed

## Freshness semantics
Caller supplies explicit `now`, `healthy_within_seconds`, and `degraded_within_seconds`.

- thresholds are strict positive integers; booleans are rejected
- degraded threshold must be >= healthy threshold
- future heartbeats fail closed
- age <= healthy threshold => `HEALTHY`
- healthy threshold < age <= degraded threshold => `DEGRADED`
- age > degraded threshold => `FAILED`
- timezone offsets and fractional seconds are normalized deterministically

## Gate
- first isolated run retained as failure evidence: 17 PASS / 1 FAIL, exit 1
- corrected isolated suite: 18/18 PASS, exit 0
- full F01-F05 regression: 88/88 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS

Evidence: `evidence/f05/`.
F05 = PASS.
