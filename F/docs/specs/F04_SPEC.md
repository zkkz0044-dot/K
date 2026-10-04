# KK/F v0.1 Specification — F04 Durable Runtime Checkpoint

Status: PASS

## Scope
F04 provides one durable, machine-parseable local runtime checkpoint. It persists only explicit runtime state and opaque JSON payload; it does not infer health, authorize control, schedule work, or contact external services.

## Format
The checkpoint is exact JSON with fields: `version`, `generation`, `status`, `payload`, `checksum`.

- version is frozen at `0.1`
- generation is a non-negative integer and must strictly increase when replacing an existing checkpoint
- status must be an exact F01 runtime status
- payload must be a finite JSON object
- checksum is SHA-256 over canonical JSON of version/generation/status/payload

Unknown fields, duplicate keys, unsupported versions, non-finite values, corrupt JSON, checksum mismatch, or a corrupt existing checkpoint fail closed.

## Durability
Writes use a same-directory temporary file, flush + fsync, atomic `os.replace`, and directory fsync. If replacement fails, the prior checkpoint remains intact and the temporary file is cleaned.

## Gate
- isolated checkpoint suite: 15/15 PASS, exit 0
- full F01+F02+F03+F04 regression: 70/70 PASS, exit 0
- Python compile check: exit 0
- static external-dependency audit: PASS
- simulated atomic-replace failure preserves the prior verified checkpoint

Evidence: `evidence/f04/`.
F04 = PASS.
