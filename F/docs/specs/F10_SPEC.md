# KK/F v0.1 Specification — F10 Local Process Candidate Integrity Preflight

Status: PASS

## Scope
F10 verifies that an F09 launch specification points to the exact local executable and working directory declared by the candidate before any later process executor may launch it. F10 does not execute or signal processes and does not use network/cloud/AI/SSH/Bridge services.

## Verification semantics
- the F09 process spec must validate first
- executable and cwd are checked with `lstat`
- executable must be a regular non-symlink file
- cwd must be a real non-symlink directory
- executable must have at least one execute bit
- executable must not be group-writable or world-writable
- executable bytes are hashed locally using SHA-256 and must exactly match the declared F09 digest
- missing/inaccessible paths and read failures fail closed
- successful result reports verified=true, path, cwd, digest, and byte size

## Boundary
This segment narrows the launch race but does not eliminate TOCTOU between preflight and a later exec call. A later executor must perform a final integrity check immediately before direct non-shell process creation.

## Gate
- isolated integrity-preflight suite: 13/13 PASS, exit 0
- full F01-F10 regression: 158/158 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS

Evidence: `evidence/f10/`.
F10 = PASS.
