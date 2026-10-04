# KK/F Stability Reinforcement — FS03 Durable Release Role State

Status: IN_PROGRESS

## Purpose
Provide one authoritative, deterministic, durable machine-readable record of the release identities occupying ACTIVE, CANDIDATE, and LAST_KNOWN_GOOD (LKG) roles. FS03 stores identities only; it does not stage bytes, activate releases, execute candidates, or roll back.

## Frozen schema
State file `release-state.json`, version `0.1`, exact fields: `version`, `generation`, `active`, `candidate`, `last_known_good`, `checksum`.
A release identity is either null where allowed or an exact object: `release_id`, `manifest_sha256`.

## Invariants
- generation is strict integer >=0 and must increase on replacement.
- ACTIVE and LKG are always non-null after initialization.
- CANDIDATE may be null.
- Initial state requires ACTIVE == LKG and CANDIDATE == null.
- Candidate declaration cannot equal ACTIVE or existing CANDIDATE.
- Clearing candidate preserves ACTIVE/LKG.
- State checksum covers all authority-bearing fields using canonical finite JSON.
- Duplicate keys, unknown fields, unsupported version, malformed identities, checksum mismatch, missing/corrupt existing state fail closed.
- Writes use same-directory temp, file fsync, atomic replace, directory fsync; replace failure preserves prior verified state.
- Runtime operation is local only; no network/cloud/AI/SSH/Bridge dependency.

## Gate
Adversarial isolated tests + repeated stability runs + full regression + compile/static audit. Raw failures retained.
