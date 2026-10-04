# FKP02 — K Audit Monotonic Witness / Rollback & Fork Defense

Status: PASS

## Architectural decision
Do not alter FH03 monotonic_witness VERSION=0.1 exact four-channel schema.
Add a separate F-owned K-audit witness extension under /root/K/F.

## PASS gate
1. F independently validates every K02 audit event; K cannot merely assert a digest.
2. New event sequence must be exactly witness generation + 1.
3. New event prev_sha256 must equal F-witnessed head digest.
4. F recomputes entry_sha256 from exact bounded event fields before accepting it.
5. Rollback, same-generation divergence, rollback-then-fork, gaps, forged hashes and replay fail closed.
6. Witness state is root-owned/non-world-writable, atomic and outside K write scope.
7. Runtime peer must be the dedicated non-root kk-k-runtime.service cgroup; root/dev bridge is denied.
8. Production K audit wrapper fails closed unless each new soul audit event becomes witness-confirmed MATCH.
9. Original FH03 four-channel tests remain PASS unchanged.
10. K/F/FK regressions, compile, fresh FP06 and repeated fault campaigns PASS.
11. Failures are preserved. No next large section begins before user verification.
