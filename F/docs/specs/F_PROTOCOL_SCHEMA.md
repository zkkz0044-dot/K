# KK/F Protocol Schema — F01

Canonical protocol version: `0.1`.

Validation is implemented by `src/kk_f/contracts.py` using Python standard library only. The validator is intentionally strict:
- exact top-level key set
- exact error-object key set
- supported protocol version only
- enumerated roles/kinds/statuses/error codes only
- lowercase canonical UUID message id
- timezone-aware RFC3339 timestamp
- object payload only
- boolean `retryable` only
- string error message only
- object error detail only

Any ambiguity or unknown field is a validation failure.
