# KK/F Production Hardening — FP03 Durable Exponential Restart Backoff

Status: PASS

## Purpose
Prevent rapid restart storms with a deterministic exponential backoff whose state survives supervisor restart. Backoff state is persisted inside the existing restart-ledger checkpoint; it is never memory-only.

## Durable state
- restart ledger schema advances to version 0.2
- add `last_attempt_at` = null or strict RFC3339 timestamp
- `attempts` and `last_attempt_at` are committed atomically in the same checkpoint generation before replacement launch
- supervisor restart cannot reset backoff progress

## Policy
- explicit `now` input only; no host clock dependency
- delay after N durable attempts: `min(base_delay * 2**(N-1), max_delay)` for N >= 1
- attempts=0 or last_attempt_at=null => no waiting
- retry before deadline => WAIT_BACKOFF, no attempt increment, no launch
- at/after deadline => next attempt may be durably consumed
- exhausted restart budget still yields HOLD_FAILED
- positive finite deterministic delay parameters only

## PASS gate
- persistence survives re-read/new supervisor object
- exact boundary tests for exponential sequence and max cap
- early retry does not mutate ledger or launch
- allowed retry commits attempt+timestamp before launch
- full regression PASS and py_compile PASS
