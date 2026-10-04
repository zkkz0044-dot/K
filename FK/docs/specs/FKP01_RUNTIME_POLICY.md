# FKP01 Runtime Policy

- F gateway execution domain: `kk-fk-gateway.service`, root/F-owned, AF_UNIX only.
- K execution identity: systemd `DynamicUser`, exact cgroup `kk-k-runtime.service`, UID must be non-zero.
- K authority view: `/run/kk-k-ro`, read-only bind of `/root/K/K`; canonical project identity remains `/root/K/K`.
- Host `/root` mode is not relaxed. K runtime cannot see `/root/K/F` or `/root/K/FK`.
- Root/development-bridge callers are rejected by F peer authentication.
- A03 remains absent from live `ENABLED_ACTIONS` pending user verification of FKP01.
- Human approval is root/F-issued, A03-only, max 300 seconds, 0600, one-use, consumed before execution.
- K06 continues to return `REQUIRE_HUMAN` for A03 before any F transport in the current production path.
- K remains the final substantive decision authority. F deterministically enforces fixed execution/integrity preconditions. No model/API/tool output can create or modify an approval.
