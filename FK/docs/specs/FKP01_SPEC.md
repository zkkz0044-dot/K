# FKP01 — Dedicated K Runtime Identity + Single-Use Human Approval

Status: PASS
Purpose: close the first privileged FK seam without weakening F or /root isolation.

## PASS gate
- K runs as systemd DynamicUser, never UID 0.
- Peer identity is exact `kk-k-runtime.service` cgroup plus SO_PEERCRED non-root.
- `/root` permissions are not relaxed and no permanent account is created.
- K sees only a read-only bind mirror of `/root/K/K` at `/run/kk-k-ro`.
- K cannot see `/root/K/F` and cannot write K00/K06 authority files.
- F gateway runs in its own `kk-fk-gateway.service` cgroup, not a development bridge.
- A03 production network exposure remains disabled until user verification.
- Root/F can issue only A03 approval with strict schema and TTL <= 300s.
- approval file is root-owned, mode 0600, inside `/root/K/FK/state`.
- missing, expired, malformed, writable, symlink approval fails closed.
- approval is atomically consumed before execution; crash loses permission rather than reusing it.
- one approval permits at most one A03; replay is rejected.
- approved A03 still traverses Frozen Authority -> preflight/SHA -> F11 -> typed receipt -> K verifier.
- K/F/FK regressions, compile, fresh FP06 and repeated FKP01 integration all PASS.
- failed evidence is retained; no prior accepted evidence is rewritten.
