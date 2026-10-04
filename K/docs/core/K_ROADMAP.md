# KK / K Build Roadmap

Authority: user-approved 2026-09-05.
Order: K is built and accepted standalone first; FK integration is deferred until user reviews the complete K artifact.

## Segments
- K00 — Philosophy / Constitution: stable machine-checkable constitutional invariants.
- K01 — Minimal Cognitive Kernel: one-shot load→observe→one LLM call→strict decision→boundary submit→mechanical verify→log→stop.
- K02 — Durable Structured Memory: bounded structured current state + append-only episodic records; no embeddings/auto-compression.
- K03 — World-State Snapshot: source/provenance/freshness-aware bounded observations; stale/unknown distinguished from fact.
- K04 — Model Interface: provider-independent model adapter, bounded structured deliberation contract, model output always untrusted.
- K05 — Bounded Planner: finite task graph with explicit limits, no direct execution authority.
- K06 — Action Governance: allowed intent/action selection, budgets, escalation and NO_ACTION; no free-form executable payload.
- K07 — Critic / Evidence: predeclared mechanical verification, evidence binding, assessment kept separate from PASS.
- K08 — Bounded Continuous Loop: controlled multi-cycle scheduler with hard budgets/stop conditions; no implicit infinite autonomy.

## Release rule
Every segment must define its gate before implementation, retain failed evidence, pass targeted/adversarial tests and compile checks, update authoritative state, then send one independent acceptance email. After K00-K08 all PASS, produce one complete TXT containing specs, code, tests, logs/evidence and hashes and email it to the user. FK work starts only after explicit user verification/approval.