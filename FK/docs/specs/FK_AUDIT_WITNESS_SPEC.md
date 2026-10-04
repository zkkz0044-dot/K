# FK Audit Witness — Logical Fifth Channel

Status: IN_PROGRESS
Purpose: detect rollback/divergence of K's canonical append-only audit without modifying F's accepted four-channel witness state.

## Boundary
- K never gives F a path or file payload.
- K sends only strict `{generation, digest}` commitments over a dedicated abstract AF_UNIX channel.
- F never reads `/root/K/K`.
- F stores the witness only under `/root/K/F` as root-owned, non-group/world-writable state.
- Production peer authentication is the same `kk-k-runtime.service` cgroup identity.

## Monotonic rules
- initial witness: generation 0, zero digest;
- commit must be exactly current generation + 1;
- replay/backward generation is rejected;
- generation gaps are rejected;
- state carries its own checksum and is atomically replaced + fsync'd.

## K verification
- K computes the head only from its own validated K02 hash-chained audit log;
- local generation behind F witness = `ROLLBACK_DETECTED`;
- same generation with different digest = `DIVERGENCE`;
- exact generation + digest = `MATCH`;
- no model/soul can supply generation, digest, witness state, or PASS criteria.
