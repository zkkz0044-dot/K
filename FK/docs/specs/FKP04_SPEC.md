# FKP04 — Production Human-Gated A03 + Current Action-Surface Completion

Status: PASS

Purpose: finish the current K/F authority surface without adding caller-controlled privilege.

## PASS gate
1. K06 keeps A03 in `human_required_actions`; K cannot turn that policy result into approval.
2. Only fixed `A03_RUN_F_SMOKE_TEST` may cross from `REQUIRE_HUMAN` to F for approval evaluation.
3. No caller-supplied approval boolean/token/path/argv/env/ProcessSpec/verifier exists.
4. F live gateway exposes A03 only through `_run_a03_approved()`.
5. Missing approval returns typed `HUMAN_APPROVAL_REQUIRED @ HUMAN_APPROVAL` and starts no process.
6. Root/F-issued approval remains A03-only, root-owned 0600, TTL <=300s, single-use and atomically consumed before execution.
7. Valid approval permits exactly one real A03 through Frozen Authority -> SHA/preflight -> executor -> typed receipt -> K verifier.
8. Replay, expiry, malformed/symlink/writable approval, Frozen Authority mismatch and executable SHA tamper all fail closed.
9. Approval is consumed even when a post-approval F validation/execution failure occurs; retry requires fresh human approval.
10. Root/development-bridge callers remain denied by SO_PEERCRED + exact K cgroup policy.
11. A01/A02/A04/A05 behavior remains unchanged.
12. No generic shell/service-control action is introduced; long-running control remains forbidden unless separately contracted.
13. K/F/FK full regressions, final acceptance, compile and fresh FP06 remain PASS.
14. Repeated real DynamicUser no-approval and approved/replay campaigns remain PASS.
15. All failed attempts and prechange artifacts are retained.