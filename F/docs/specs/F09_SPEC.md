# KK/F v0.1 Specification — F09 Strict Process Launch Contract

Status: PASS

## Scope
F09 freezes a strict machine-validated process launch description before any later process-control layer may execute it. F09 performs validation only: it does not read the filesystem, verify the executable hash on disk, invoke a shell, spawn processes, or contact external services.

## Exact schema
Fields: `version`, `executable`, `argv`, `cwd`, `env`, `sha256`.

- version is frozen at `0.1`
- executable is a non-empty NUL-free absolute POSIX path
- cwd is a non-empty NUL-free absolute POSIX path
- argv is a JSON list of non-empty NUL-free strings
- env is an object whose keys match POSIX-style environment variable names and whose values are NUL-free strings
- sha256 is exactly 64 lowercase hexadecimal characters
- no shell field exists; unknown or missing fields fail closed

## Security boundary
F09 does not interpret shell metacharacters because it defines argv as data, not a shell command string. A later executor must preserve that property by using direct exec-style process creation with `shell=False` or equivalent and must verify the declared executable digest before launch.

## Gate
- isolated process-spec suite: 15/15 PASS, exit 0
- full F01-F09 regression: 145/145 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS

Evidence: `evidence/f09/`.
F09 = PASS.
