# KK/F Stability Reinforcement — FS01 Strict Release Manifest

Status: PASS

## Purpose
FS01 freezes a deterministic, machine-verifiable identity for an immutable local F release. It is the foundation for later candidate staging, Last-Known-Good tracking, atomic activation, and rollback. FS01 does not activate, replace, delete, execute, or authorize a release.

## Manifest schema
Exact top-level fields:
- `version`: exactly `0.1`
- `release_id`: canonical lowercase UUID
- `entrypoint`: strict normalized relative POSIX path
- `files`: non-empty lexicographically sorted list of exact file records
- `manifest_sha256`: lowercase SHA-256 over canonical JSON of the other four fields

Exact file-record fields:
- `path`: strict normalized relative POSIX path
- `sha256`: lowercase 64-hex SHA-256
- `size`: strict non-negative integer

## Invariants
- unknown or missing fields fail closed
- duplicate JSON keys fail closed
- non-finite JSON fails closed
- absolute paths, empty paths, `.`/`..`, repeated separators, backslashes, NULs, and non-normalized paths fail closed
- file paths are unique and sorted lexicographically
- `entrypoint` must name one of the declared files
- boolean/type-confusion values fail closed where integers/strings are required
- manifest checksum must exactly match canonical finite JSON material
- validation performs no process execution, network access, dynamic import, or mutation
- loading is read-only and UTF-8 strict

## Gate
- isolated adversarial suite PASS
- 20 consecutive isolated repetitions PASS
- full pre-existing F01-F20 + FP01-FP06 regression PASS
- Python compile PASS
- static external-dependency/mutation audit PASS
- raw evidence retained under `evidence/fs01/`

Gate result: PASS
