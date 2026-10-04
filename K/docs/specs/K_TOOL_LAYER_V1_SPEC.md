# K-Compatible Tool Layer v1

## Purpose

Provide one strict, auditable tool namespace above the accepted K→FK→F chain.
The tool layer is an abstraction only; it grants no new authority.

## Non-negotiable boundary

- K must never execute host commands, process specs, paths, or environment values directly.
- Every executable tool maps to an already accepted K action ID.
- The existing FK gateway remains authoritative for deterministic transport/execution validation; it does not hold independent cognitive veto authority over valid K decisions.
- Unknown tools and extra request fields fail closed.
- Adding a registry entry cannot create a new action ID.
- Human-gated F actions remain human-gated after tool wrapping.

## v1 request

```json
{"schema":"K.TOOL.REQUEST.1","tool":"kk.project_state.read"}
```

## v1 receipt

The tool layer wraps the original FK receipt without discarding it.
`verified=true` is only emitted when the FK receipt outcome is `PASS`.
