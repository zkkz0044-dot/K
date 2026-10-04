# FKP08 — Database Read-only Contract

## Status
Backend discovery found no K project database or database connection configuration.

## Contract
- Tool remains `database.query.readonly` and remains disabled.
- K never submits raw SQL.
- Requests name an approved dataset + approved view + bounded primitive filters + bounded limit.
- The adapter, once bound, owns the fixed SQL/query implementation.
- Unknown datasets/views/filters fail closed.
- Backend writes, DDL, transactions, stored procedures, arbitrary functions and free-form SQL are forbidden.

## Current behavior
Until a concrete database is bound, every valid request returns `VETO / DATABASE_BACKEND_UNBOUND`.

## Security purpose
This prevents a future model from turning a nominally read-only database tool into an arbitrary SQL execution surface.
