# KK/F Stability Reinforcement — FS07 Durable SAFE_MODE Failure Latch

Status: IN_PROGRESS

## Purpose
Prevent repeated recovery faults from causing endless state/pointer churn. A local durable failure counter deterministically latches SAFE_MODE at a fixed caller-supplied threshold. SAFE_MODE blocks FS06 reconciliation until an explicit generation-matched acknowledgement clears it.

## Invariants
- exact versioned safety-state schema: version,generation,mode,consecutive_failures,reason,checksum.
- modes only NORMAL / SAFE_MODE; reason null in NORMAL and `RECOVERY_FAILURE_LIMIT` in SAFE_MODE.
- threshold strict integer >=1; booleans rejected.
- each failed FS06 reconciliation durably increments failure count exactly once.
- reaching threshold latches SAFE_MODE in same durable generation update.
- while SAFE_MODE, guarded reconciliation never calls FS06 and never mutates release authority/pointer.
- a successful reconciliation while NORMAL resets a nonzero failure count; zero count success is idempotent/no write.
- SAFE_MODE never auto-clears due success/restart/time.
- explicit clear requires exact observed generation plus literal boolean acknowledgement=True; stale generation/type confusion rejected.
- state corruption/missing state fails closed.
- writes: file fsync + atomic replace + directory fsync.
- no network/cloud/AI/SSH/Bridge runtime dependency.
