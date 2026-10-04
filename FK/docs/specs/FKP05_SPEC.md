# FKP05 — Final K/F Merge Acceptance

Status: PASS

## PASS gate
1. `/root/K` remains the single canonical KK home; no old roots or project copies are reintroduced.
2. The full defined action surface A01-A05 is live; A03 remains human-gated; F mechanically enforces the fixed approval/integrity preconditions but does not independently overrule a valid K decision.
3. K never supplies ProcessSpec, path, argv, env, verifier, approval token or approval boolean to F.
4. K runs non-root in exact `kk-k-runtime.service` cgroup; root/dev peers are denied.
5. F gateway and F-owned K Audit Witness are persistent system services recoverable after manager/service restart.
6. Persistent unit source files remain under `/root/K`; outside the project only systemd registration symlinks are allowed.
7. K Audit Witness canonical history survives service restart and rejects rollback/fork/replay.
8. A03 missing/expired/replayed approval, peer spoof, authority mismatch and SHA tamper all fail closed.
9. One valid approval permits exactly one A03; failure after approval consumption never restores permission.
10. K verifier rejects forged/mismatched/unknown receipts and preserves typed F VETO reasons.
11. Gateway/witness process termination self-heals without changing policy or canonical state.
12. No generic shell, arbitrary process, generic service-control or cross-project action exists in the registry.
13. F's original four-channel monotonic witness schema remains unchanged.
14. K/F/FK full regressions, final acceptance, compile and fresh FP06 all PASS after persistent installation.
15. Final live campaigns cover safe action, no-approval A03, approved A03, replay, peer denial, restart recovery and audit continuity.
16. All failures from FKP01-FKP05 remain preserved; no failed evidence is rewritten as success.