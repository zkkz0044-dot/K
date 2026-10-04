# K Authority Hardening

Status: PARTIAL_PASS_BLOCKED_BEFORE_PRIVILEGED_FK

PASS:
1. K authority reader requires root-owned regular files.
2. Group/world writable authority files are rejected.
3. Leaf and parent symlink/path-swap attacks are rejected.
4. Paths outside `/root/K/K` are rejected.
5. K00/K06 authoritative loads use this guard.
6. Targeted authority tests PASS and K full regression remains PASS.

BLOCKED:
- Dedicated non-root K runtime identity cannot be created in this session because the remote command policy blocks account-creation operations.
- Therefore privileged FK action A03 remains network-disabled.

No workaround may weaken `/root` permissions or reuse a generic shared identity as if it were dedicated K.

FKP01 acceptance evidence:
- systemd DynamicUser non-root runtime: PASS.
- read-only authority mirror `/run/kk-k-ro`: PASS.
- `/root` remains 0700; F tree hidden from K runtime.
- root ownership/mode/symlink/path-swap checks remain enforced.
- full K regression 175/175 PASS.
