# KK/F Stability Reinforcement — FS06 Deterministic Interrupted-Activation Recovery

Status: IN_PROGRESS

## Purpose
Reconcile durable FS03 authority state, release bytes, and FS05 `current` pointer after crash/power-loss interruption. Durable authority is primary; only independently verified bytes may become current.

## Deterministic rules
1. Read and verify FS03 state fail-closed.
2. Resolve local FS01 manifests for required release identities and require exact identity match.
3. If authoritative ACTIVE bytes pass FS02, `current` is repaired to ACTIVE whenever it differs/malformed. Authority state is not advanced merely because pointer names CANDIDATE.
4. If ACTIVE bytes fail but LKG differs and passes FS02, commit authority rollback to LKG first (generation+1, CANDIDATE cleared), then repair current to LKG.
5. If neither ACTIVE nor a distinct verified LKG is usable, fail closed; do not guess or promote CANDIDATE.
6. No release bytes are modified/deleted; no external/network/AI/SSH/Bridge dependency.

Crash semantics
- pointer switched to CANDIDATE but state not committed -> restore pointer to authoritative ACTIVE.
- state committed to new ACTIVE but pointer remained old -> restore pointer to committed ACTIVE.
- rollback state committed but pointer switch interrupted -> next recovery retries pointer repair to now-authoritative LKG.
