# Roadmap: experiments worth contributing

The priorities below are proposed work, not completed features.

| Priority | Contribution | Evidence of progress |
|---|---|---|
| 1 | Reproducible first-run systemd deployment in a disposable VM | Fresh setup log, service receipts, cleanup/recovery verification |
| 2 | Local inference provider behind the existing model gateway | Role/schema compatibility and offline connection receipt |
| 3 | Independent cognition evaluation | Unseen tasks, independent scoring, separate fallback and model results |
| 4 | Cross-model continuity experiments | Preserved identity/history, explicit model transition, measured answer differences |
| 5 | Long-document memory and recall | Fresh long-document tasks with measured retrieval coverage and failure cases |

Start with a small reproducible issue. Say which layer owns the change, which
contract it preserves, and what independent observation would show it works.
Keep model output, policy checks, and factual verification separate.

For a new provider, contribute transport and role compatibility before changing
K's identity or giving model output additional authority. For an evaluation,
publish synthetic/public inputs and the scoring method; keep private histories
and credentials out of the repository.
