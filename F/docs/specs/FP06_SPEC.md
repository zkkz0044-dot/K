# KK/F Production Hardening — FP06 Full Fault/Recovery Acceptance

Status: PASS

## Purpose
Prove the hardened F runtime can cold-start, supervise a real worker, survive worker crashes with durable backoff, preserve restart budget across supervisor restarts, fail closed on corruption, and operate without network access.

## Required scenarios
- cold start from absent ledger/evidence with real worker and heartbeat
- duplicate supervisor lock contention
- worker crash -> bounded automatic replacement
- repeated crash before backoff deadline -> no premature replacement
- replacement at/after deadline -> next durable attempt
- budget exhaustion -> one durable HOLD_FAILED transition and no restart storm
- supervisor restart with non-pristine ledger preserves attempts/backoff/HOLD_FAILED
- corrupt ledger/evidence fails closed
- stale heartbeat cannot be inherited as health proof for a replacement worker
- isolated network namespace operation succeeds
- real systemd service uses non-root identity and root-owned readable authority/config

## PASS gate
All scenarios above verified with raw evidence, full regression, Python compile, and no dependency on Bridge/SSH/cloud/AI/network for runtime survival.
