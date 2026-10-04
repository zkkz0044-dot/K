# KS01 — Strict Three-Soul Cognition Layer

Status: PASS
Purpose: formalize Soul A / Soul B / Soul C as bounded untrusted cognition before K governance.

## Roles
- Soul A / Proposer: emits bounded assessment + pre-approved candidate Action IDs only.
- Soul B / Critic: independently challenges A with bounded objections + blocked Action IDs only.
- Soul C / Judge: selects one Action ID only from Soul A's candidate set, or A05_NO_ACTION.

## Authority
- Every soul output is `UNTRUSTED_CANDIDATE`.
- No soul has shell, file, process, FK, verifier, path, argv, env, hash, timeout, or parameter authority.
- Soul C cannot bypass K06 Governance or the deterministic F execution/integrity guard.
- Provider/model identity never becomes a trust root.

## Orchestration
- exactly one call to A, then one call to B, then one call to C;
- no implicit retry or provider fallback;
- only parsed bounded structured outputs are passed between roles;
- raw chain-of-thought is neither required nor persisted;
- any malformed role output fails closed before governance/F.
