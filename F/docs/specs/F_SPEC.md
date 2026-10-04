# KK/F v0.1 Specification — F01 Core Contract

Status: PASS

## Scope
F01 freezes only the cross-component vocabulary and validation boundary: roles, statuses, protocol version, error codes, and message envelope. It does not implement Worker, Supervisor, Frozen Authority, cloud fencing, upgrade, rollback, or lifecycle management.

## Roles
- `frozen_authority`
- `worker`
- `supervisor`
- `operator`
- `external_controller`

## Status vocabulary
Project/gate statuses:
`NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, `PARTIAL_PASS`, `PASS`, `CANDIDATE`, `REJECTED`, `ACCEPTED`.

Runtime message statuses:
`READY`, `RUNNING`, `HEALTHY`, `DEGRADED`, `BLOCKED`, `FAILED`, `STOPPED`.

## Protocol
Protocol version: `0.1`.
Every message is a strict JSON object with exactly these top-level fields:
- `protocol_version`
- `message_id`
- `kind`
- `source_role`
- `target_role`
- `timestamp`
- `status`
- `payload`
- `error`

No additional top-level fields are accepted.

`message_id` must be a lowercase canonical UUID string.
`timestamp` must be strict RFC3339 with an explicit timezone.
`payload` must be an object.
`error` must be null or a strict error object.

## Message kinds frozen in F01
- `heartbeat`
- `progress`
- `result`
- `fault`
- `control_request`
- `control_result`

## Error object
Exactly:
- `code`
- `message`
- `retryable`
- `detail`

Allowed F01 error codes:
- `INVALID_SCHEMA`
- `UNSUPPORTED_PROTOCOL`
- `UNKNOWN_ROLE`
- `UNKNOWN_STATUS`
- `UNKNOWN_KIND`
- `ILLEGAL_TRANSITION`
- `INTEGRITY_FAILURE`
- `TIMEOUT`
- `RESOURCE_LIMIT`
- `AUTHORITY_DENIED`
- `INTERNAL_ERROR`

Unknown values and type-confusion inputs are rejected fail-closed as `ContractError`.

## Gate
Automated adversarial suite: 23/23 PASS.
Evidence: `evidence/f01/test-round2-pass.json`.
F01 = PASS.
