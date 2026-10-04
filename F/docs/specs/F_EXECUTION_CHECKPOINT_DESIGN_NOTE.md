# F Execution Checkpoint — Design Candidate

Status: DESIGN_CANDIDATE_ONLY
Runtime impact: NONE
KB01 impact: NONE
Source confidence: MEDIUM (individual X developer report supplied by user; implementation details not independently verified here)

## Why this matters

The supplied external signal describes an "Execution Checkpoint" concept: before an agent performs a risky real-world action, persist a recoverable execution point so an error can be reverted, rather than preserving only dialogue or memory state.

This is directionally aligned with F's existing deterministic design, but it should not be copied as authority. It is retained only as evidence that execution-level rollback is becoming a serious Agent-safety design direction.

## What F already has

Current F already contains several transaction-like mechanisms:

1. Release state has candidate/commit/rollback-to-LKG semantics.
2. Monotonic witness has PREPARE/COMMIT/recovery semantics for protected state transitions.
3. Transaction recovery removes incomplete temporary state and fails closed.
4. FKP04 A03 human approval is single-use and is consumed before execution; permission does not silently return after later failure.

These mechanisms are real, but they are not yet a generic per-action execution checkpoint layer.

## Gap to evaluate after KB01

Current A03 real execution path is essentially:

HUMAN APPROVAL -> FROZEN AUTHORITY -> PREFLIGHT -> EXECUTE -> RECEIPT

There is no general F-owned execution transaction object that mechanically binds, before side effect:

- action_id
- authority_id / authority digest
- executable or action implementation digest
- pre-execution state digest
- rollback or compensation class
- idempotency key
- checkpoint generation
- execution result
- commit/rollback terminal state

## Proposed deterministic state machine

For future reversible privileged actions, evaluate:

PREPARE
  -> CHECKPOINT
  -> EXECUTE
  -> VERIFY
  -> COMMIT
       or
     ROLLBACK

Crash recovery must be defined for every boundary:

- crash before CHECKPOINT: no execution allowed
- crash after CHECKPOINT before EXECUTE: recover to PREPARED/CANCELLED without side effect
- crash during EXECUTE: determine from action-specific durable evidence; never guess success
- crash after EXECUTE before COMMIT: verify actual side effect, then mechanically COMMIT or ROLLBACK/COMPENSATE
- crash during ROLLBACK: resume only from durable rollback state

## Critical limitation

"Checkpoint" must never be marketed internally as universal undo. Some external actions are inherently irreversible or only compensatable, for example:

- sending an email/message
- external payments/transfers
- publishing to a third-party platform
- destructive remote API calls

Therefore every F action should eventually declare one fixed execution class, owned by F authority:

- REVERSIBLE
- COMPENSATABLE
- IDEMPOTENT_NONREVERSIBLE
- IRREVERSIBLE

IRREVERSIBLE actions should require stronger PREPARE gates and explicit human authorization where applicable; they cannot claim ROLLBACK if reality cannot be restored.

## Suggested acceptance gate for a future F segment

Do not implement during KB01 soak. After KB01, a future segment may be accepted only if all of the following pass:

1. F-owned exact checkpoint schema; K/model cannot choose checkpoint path, rollback handler, verifier, or authority.
2. Checkpoint persisted+fsynced before real side effect.
3. Action-specific deterministic rollback/compensation policy.
4. Monotonic generation and replay/fork protection.
5. Crash injection at PREPARE/CHECKPOINT/EXECUTE/VERIFY/COMMIT/ROLLBACK boundaries.
6. No silent retry of non-idempotent actions.
7. Approval consumption semantics remain one-time and are not restored by rollback.
8. Receipt distinguishes EXECUTED, COMMITTED, ROLLED_BACK, COMPENSATED, VETO, and UNKNOWN_FAIL_CLOSED as appropriate.
9. Irreversible actions fail closed if their real-world result cannot be proved.
10. Full K/F/FK regression and fresh FP06 remain PASS.

## Current decision

KEEP AS DESIGN CANDIDATE.
DO NOT MODIFY PRODUCTION F DURING KB01.
REVISIT AFTER KB01 SURVIVAL QUALIFICATION.
