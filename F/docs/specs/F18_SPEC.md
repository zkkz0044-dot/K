# KK/F v0.1 Specification — F18 Local Frozen Authority Manifest Gate

Status: PASS

## Scope
F18 establishes a local Frozen Authority boundary for F process candidates. A root-owned, non-symlink, non-group/world-writable manifest explicitly authorizes exactly one executable path, SHA-256 digest, and bounded restart budget.

## Semantics
- authority manifest path must be absolute
- manifest must be a real regular file, not a symlink
- manifest must be owned by uid 0
- manifest must not be group- or world-writable
- strict JSON with duplicate-key rejection and exact schema
- version/authority_id/executable/sha256/max_restart_attempts strictly validated
- candidate must first satisfy F09 launch contract
- candidate executable path must exactly equal authorized path
- candidate SHA-256 must exactly equal authorized digest
- restart budget originates from Frozen Authority manifest
- candidate cannot authorize itself by changing its process spec
- no network/cloud/AI/SSH/Bridge runtime dependency

## Gate
- isolated suite: 12/12 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F18 regression: 239/239 PASS, exit 0
- Python compile: exit 0
- static authority-boundary audit: PASS, exit 0

Evidence: `evidence/f18/`.
F18 = PASS.
