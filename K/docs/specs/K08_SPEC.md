# K08 — Bounded Continuous Loop / Final Standalone Acceptance

Status: PASS
Purpose: allow repeated K cognition cycles only inside explicit hard budgets and stop conditions.

## Scope
- explicit max_cycles 1..32; no unbounded while loop;
- each cycle asks for at most one proposed Action ID;
- every proposed action passes K06 governance before any executor call;
- an allowed A05_NO_ACTION still traverses the same executor/result path, then stops;
- FAIL/VETO/REJECTED, DENY, REQUIRE_HUMAN, policy STOP, proposer error, executor error all stop the run;
- no implicit retry after any failure;
- bounded durable cycle log;
- standalone executor only; real F/FK is not attached.

## PASS gate
- hard cycle limit cannot be bypassed by proposer/executor;
- max one proposer call and max one executor call per cycle;
- NO_ACTION is a normal governed action and stops after its mechanical result;
- all failure/veto/human/policy/error states stop without retry;
- loop log records each attempted cycle;
- integrated K00-K08 standalone acceptance passes with mock model + mock F-shaped transport;
- soak/repeat + full K regression + compile PASS;
- all K00-K08 PASS; final standalone K acceptance ACCEPTED;
- real F remains untouched; FK stays deferred until user reviews final TXT.