# KK/F Adversarial Hardening — FH03 Privilege-Separated Monotonic Witness

Status: IN_PROGRESS

## Purpose
Add a local privilege-separated monotonic witness so durable F state cannot be silently replaced by an older previously-valid state across supervisor restarts.

## Threat boundary
Protects against filesystem rollback/replay and stale-snapshot restoration by the unprivileged F runtime identity. It does not claim protection after root compromise, kernel compromise, or an attacker that can legitimately invoke every authorized forward state transition as F.

## Design
- F runtime remains non-root.
- a minimal deterministic root witness owns a root-only durable state file.
- runtime communicates over a local Unix socket using strict exact JSON and peer-credential UID validation.
- witness channels are fixed: `restart_ledger`, `evidence`, `release_state`, `safety_state`.
- generation/count can only increase; exact digest is bound to each committed generation.
- two-phase PREPARE -> state mutation -> COMMIT prevents crash windows from creating ambiguous authority.
- pending recovery accepts only exact old committed state (abort) or exact prepared new state (commit); anything else fails closed.
- no shell, subprocess, network, dynamic execution, arbitrary path operations, or user-selected commands in witness.

## FH03 PASS gate
- strict protocol/schema/type confusion tests PASS.
- same/lower generation replay rejected.
- old valid snapshot restored after witness advance rejected across fresh client/restart simulation.
- prepared crash windows converge only to exact old or exact new digest; third state fails closed.
- unauthorized peer UID rejected in real Unix-socket integration.
- root witness state permissions and atomic fsync persistence verified.
- integration protects production restart ledger and evidence anchors without weakening F01-FH02.
- full regression, compile, fresh production fault injection PASS.
