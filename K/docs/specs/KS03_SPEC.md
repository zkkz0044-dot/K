# KS03 — Three-Soul K08 Integration / Adversarial Acceptance

Status: PASS
Purpose: make the accepted three-soul cognition path the bounded proposer used by K08.

## Canonical path
Soul A → Soul B → Soul C → KS02 evidence gate → K08 → K06 Governance → FK → F.

## Invariants
- soul proposer returns only one pre-approved Action ID;
- soul proposer has no FK client, executor, shell, path or process authority;
- each cycle uses at most one A call, one B call and one C call;
- malformed soul/evidence/provider failure becomes K08 PROPOSER_ERROR with no executor call;
- KS02 safe fallback returns A05_NO_ACTION;
- A03 remains K06 REQUIRE_HUMAN before any FK transport;
- no implicit retry is introduced by the soul layer;
- bounded soul audit is appended through K02 hash-chained memory.

## PASS gate
- targeted/adversarial tests PASS;
- real safe FK action works through three-soul → K08 → K06 → live F gateway;
- A03 through the same path proves zero F transport calls;
- soak/repeat PASS;
- full K, full F, full FK, compile and fresh FP06 remain PASS.
