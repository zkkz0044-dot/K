# KK/F Production Hardening — FP04 Dry-Run + Isolated Self-Test

Status: PASS

## Dry-run contract
- Frozen Authority authorization is real and mandatory.
- Process candidate integrity preflight is real, including reading the executable and recomputing SHA-256 from disk.
- Restart/backoff planning is pure read-only. It may read production ledger state but must not call any mutating ledger API.
- No `subprocess.Popen`, no worker start/stop/kill, no production ledger mutation, no production evidence append, no restart-attempt consumption.
- Dry-run returns a deterministic plan describing the action that would be taken.

## Self-test contract
- Self-test is a separate mode, not a relaxed dry-run.
- It must use a dedicated Frozen Authority manifest for a dedicated test executable.
- It must use isolated temporary lock, ledger, work and evidence paths.
- It must exercise real process launch/stop and real evidence append inside that isolated namespace.
- It must never reuse production authority, production ledger, production lock, production evidence or a production worker.

## PASS gate
- Dry-run proves executable digest from real disk bytes.
- Dry-run backoff/restart planning is read-only and leaves ledger/evidence byte-for-byte unchanged.
- Tests fail if dry-run reaches `Popen`, stop/kill, mutating ledger API, or evidence append.
- Self-test cannot run without its own valid Frozen Authority.
- Self-test uses real Popen and real isolated evidence/ledger, then cleans up its worker.
- Existing F01-F20 + FP01-FP03 regression remains PASS.
- Python compile check PASS.
