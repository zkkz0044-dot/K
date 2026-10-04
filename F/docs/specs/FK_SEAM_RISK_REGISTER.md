# FK Seam Risk Register

Status: ACTIVE / RELEASE-BLOCKING ITEMS IDENTIFIED
Date: 2026-09-05

## R1 — Mock-F to real-F semantic gap
Severity: CRITICAL
Release blocker: YES
Verified fact: K standalone acceptance injects callable mock transports/receipts; K has never exercised a production F gateway.
Required closure: new integration tests must prove K action_id -> real F-owned gateway -> real F validation/authority path -> real typed receipt. Separate K PASS + F PASS is not accepted as FK PASS.

## R2 — Action translation/mapping is a new authority surface
Severity: CRITICAL
Release blocker: YES
Required closure: mapping is F-owned, static, exact-schema, action-ID only. K supplies no process spec/path/argv/env/hash/verifier/timeout. Any action that launches a process must resolve only to a predeclared F-owned authority entry and still traverse F authorization, launch guard/preflight and the correct execution lifecycle. No string-building or dynamic ProcessSpec construction from K input.

## R3 — One-shot K semantics vs supervised F lifecycle
Severity: HIGH
Release blocker for current A01-A05: NO, if scope remains bounded
Decision: FK01-FK04 may expose only read/no-op/fixed-log/fixed one-shot smoke semantics. No action controlling a long-lived supervised worker may reuse F11 one-shot semantics. A future supervised-control action needs its own state-transition contract with runtime_cycle/health supervisor convergence evidence.

## R4 — VETO reason fidelity
Severity: HIGH
Release blocker: YES
Current gap: K verifier knows only a small generic VETO enum while F components mostly raise typed exceptions/messages rather than a unified gateway reason taxonomy.
Required closure: gateway defines a bounded stable F-owned reason-code taxonomy (for example AUTHORITY_MISMATCH, EXECUTABLE_SHA256_MISMATCH, PATH_POLICY_DENY, RESTART_BUDGET_EXHAUSTED, PEER_AUTH_DENY, REQUEST_SCHEMA_INVALID). Receipt carries the stable code and validation stage. Raw exception text is NOT forwarded as protocol authority.

## R5 — K policy/constitution runtime immutability
Severity: HIGH
Release blocker for initial A05/A01/A02 bring-up: NO
Required before privileged production actions: YES
Verified fact: K00/K06 files are root:root 0644, so ordinary non-root cannot modify them, but K loaders do not verify owner/mode like F Frozen Authority and no final non-root/read-only production K unit exists yet.
Required closure: K authority loader validates root ownership + no group/world write; production K runs dedicated non-root identity; K00/K06/isolation authority files exposed read-only; mutation attempts are adversarially tested.

## R6 — K audit rollback not witnessed
Severity: HIGH
Release blocker for first FK bring-up: NO
Verified fact: F monotonic witness currently has exactly four channels: restart_ledger, evidence, release_state, safety_state. K decision/execution logs are outside it.
Decision: defer to explicit post-merge hardening phase; do not silently ignore. Preferred design is a fifth monotonic digest/generation channel for K audit state, added only through a separate F change with full F regression/fault-injection acceptance.

## Release decision
FK cannot be declared ACCEPTED until R1, R2 and R4 are closed with real integration evidence.
R3 is constrained by scope: supervised-process control remains forbidden.
R5 must close before K receives privileged production actions.
R6 is scheduled post-merge hardening and remains explicitly OPEN until accepted or deliberately rejected by user.
