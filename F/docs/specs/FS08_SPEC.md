# KK/F Stability Reinforcement — FS08 Integrated Soak, Fault Injection, and Final Acceptance

Status: IN_PROGRESS

## Purpose
Final integrated stability gate for FS01-FS07. No new runtime authority is introduced. FS08 repeatedly exercises real local filesystem durability, release staging, activation, crash-window reconciliation, verified LKG rollback, SAFE_MODE latching/clear, and resource hygiene.

## Required integrated scenarios
1. 100 consecutive real release lifecycle cycles: build source -> FS04 stage -> FS03 candidate -> FS05 activate -> verify ACTIVE/LKG/CANDIDATE/current/tree invariants every cycle.
2. 100 interrupted-activation recoveries, alternating both FS05 crash windows: pointer switched before state commit, and state committed before pointer switch. Every case must converge deterministically under FS06.
3. 50 independent corrupt-ACTIVE scenarios must roll back only to FS02-verified distinct LKG.
4. 50 real SAFE_MODE latch/hold/explicit-generation-clear cycles driven by unrecoverable FS06 failures; SAFE_MODE must block reconciliation while latched.
5. Resource hygiene: no leaked `.stage-*`, `.current-*`, `*.tmp` artifacts after successful integrated runs; process FD count must not grow materially after repeated verification/recovery operations.
6. Fresh FS08 isolated suite must PASS, then repeated integrated runs must PASS.
7. Fresh full F01-F20 + FP01-FP06 + FS01-FS08 regression must PASS.
8. Fresh Python compile and static external-dependency audits must PASS.
9. Fresh production fault/recovery acceptance (`tools/run_fp06_fault_injection.sh`) must PASS after FS08 changes.

## Final gate
FS08 PASS only if all required scenarios and regressions pass with raw evidence retained. Final F Stability Reinforcement acceptance is ACCEPTED only after FS01-FS08 are all PASS and original F/FP acceptance remains accepted.
