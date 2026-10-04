# KK/F Production Hardening — FP02 Explicit Single-Instance Lock + FP01 Integration

Status: PASS

## Purpose
FP01 and FP02 are finalized as one combined bootstrap ownership design. A dedicated kernel-backed single-instance lock becomes the authority for whether another F supervisor instance is alive. Restart-ledger existence is no longer used as an indirect lock.

## Combined semantics
- Frozen Authority authorization and candidate preflight occur before mutable runtime state.
- Acquire a dedicated non-blocking exclusive local file lock before ledger reconciliation.
- If another holder owns the lock, bootstrap is denied without touching the ledger.
- If the lock can be acquired and the ledger is absent, initialize it normally.
- If the lock can be acquired and an exact pristine generation-0 ledger exists, treat it as an abandoned partial bootstrap and safely roll it back/reinitialize.
- If the ledger is non-pristine, corrupt, or ambiguous, fail closed; never reset it automatically.
- After successful launch, the bootstrap result retains the lock for the supervisor lifetime.
- On bootstrap exception, release the lock deterministically.
- A stale unlocked lock file is reusable without manual deletion.
- Ledger is accounting state only, not a single-instance primitive.

## Lock requirements
- absolute path only; real regular non-symlink file
- current effective uid ownership; no group/world write
- non-blocking kernel `flock` exclusive lock
- metadata written only after lock acquisition
- second concurrent holder denied
- stale unlocked file recoverable
- release deterministic/idempotent
- no network/cloud/AI/SSH/Bridge runtime dependency

## PASS gate
- real same-host contention and stale-lock recovery tests PASS
- combined bootstrap tests distinguish live lock vs abandoned pristine ledger
- non-pristine/corrupt ledger remains fail-closed
- transient spawn failure -> pristine cleanup -> retry PASS
- full regression PASS and py_compile PASS
