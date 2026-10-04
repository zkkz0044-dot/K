# K03 — World-State Snapshot / Provenance

Status: PASS
Purpose: prevent K from treating stale, missing, or source-less observations as current facts.

## Scope
- strict bounded fact records with explicit source_id, observed_at and TTL;
- deterministic snapshot built against an explicit caller-supplied time;
- FRESH / STALE / UNKNOWN are distinct states;
- duplicate fact keys fail closed rather than being silently reconciled;
- lookup preserves provenance and freshness.

## Non-goals
No web crawling, no source ranking model, no automatic conflict resolution, no hidden current-time dependency, no truth claim beyond supplied observations.

## PASS gate
- exact fact/snapshot schemas; duplicate/unknown fields fail closed;
- invalid key/source/value/time/TTL rejected;
- duplicate fact keys rejected;
- freshness boundary deterministic and tested;
- missing fact returns UNKNOWN, stale fact cannot be mislabeled KNOWN/FRESH;
- provenance survives snapshot and lookup;
- targeted/adversarial + repeat + K00-K03 regression + compile PASS;
- real F remains untouched.