# KK/F v0.1 Specification — F02 Evidence & Audit

Status: PASS

## Purpose
F02 provides a deterministic, local, machine-parseable evidence primitive for later F runtime components. It records only messages that already satisfy the frozen F01 contract and verifies integrity fail-closed.

## Store format
A store contains exactly the authoritative pair `evidence.jsonl` and `HEAD.json`. Each log entry has exactly `seq`, `prev_hash`, `record`, and `record_hash`. `record_hash` is SHA-256 over canonical JSON of `seq`, `prev_hash`, and `record`. The first entry links to 64 zeroes. Sequence starts at 1 and is contiguous.

`HEAD.json` has exactly `version`, `count`, and `last_hash`. Version is `0.1`. An empty store has count 0 and the genesis hash.

## Canonicalization and validation
JSON is UTF-8, key-sorted, compact, finite-number-only JSON. Duplicate JSON keys are rejected. Every record must pass F01 `validate_message` before append and again during verification. Unknown entry/head fields fail closed.

## Durability and integrity
Append fsyncs the log entry before atomically replacing and fsyncing HEAD. Verification recomputes every hash and checks sequence, previous-hash links, exact schemas, record validity, and HEAD/log agreement. Missing files, corruption, truncation visible against HEAD, incomplete commit, and HEAD rollback visible against the log are rejected.

## Boundary
F02 is a local integrity/audit primitive, not an adversarial external notarization system. A privileged attacker able to coherently rewrite both the entire log and HEAD is outside F02. Multi-writer concurrency is also outside F02 v0.1; callers must serialize writers until a later runtime owner exists. No network, GitHub, cloud drive, ChatGPT, Supabase, Codex inference, SSH, or development Bridge is required by F02 runtime.

## Gate
- isolated F02 adversarial suite: 19/19 PASS, exit 0
- full F01+F02 regression suite: 42/42 PASS, exit 0
- Python compile check: PASS, exit 0
- raw evidence retained in `evidence/f02/`

F02 = PASS.
