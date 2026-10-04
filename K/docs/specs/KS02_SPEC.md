# KS02 — Evidence Disagreement Gate + Bounded Soul Audit

Status: PASS
Purpose: mechanically constrain three-soul disagreement and evidence use before K06 Governance.

## Evidence contract
- Every evidence item is `UNTRUSTED_EVIDENCE`.
- Evidence is bounded, strict-schema, provenance-labelled and freshness-labelled.
- Evidence may SUPPORT or CONTRADICT only pre-approved Action IDs.
- No evidence item grants execution authority.

## Deterministic gate
For a non-NO_ACTION Soul C selection:
- Soul B must not block the selected action;
- at least one FRESH SUPPORT item must reference the selected action;
- any FRESH CONTRADICT item forces safe fallback;
- stale/unknown evidence cannot satisfy support.

Failure resolves mechanically to `A05_NO_ACTION`; it does not ask a model to reinterpret the rule.

## Audit
- append only a bounded decision summary and cryptographic digests;
- do not persist hidden/raw chain-of-thought;
- use existing K02 append-only hash-chained event memory;
- malformed evidence/audit input fails closed.
