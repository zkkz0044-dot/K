# K01 — Minimal Cognitive Kernel

Status: PASS
Implementation: STARTED
Purpose: prove one narrow, controlled cognition→F execution→mechanical verification→append-only log cycle.

## 1. Non-goals
K01 does NOT implement advanced memory, autonomous multi-step planning, continuous loops, self-modification, arbitrary shell execution, dynamic tool discovery, free-form process specs, or business-goal self-grading.

## 2. One-shot lifecycle
1. LOAD K00 constitution.
2. OBSERVE fixed-format goal and world-state files.
3. THINK with exactly one LLM call.
4. PARSE LLM output as strict Decision Schema.
5. SELECT exactly one pre-approved Action ID.
6. SUBMIT the action to F through the K→F boundary.
7. F independently validates registry entry and authority.
8. F executes the valid K-authorized action, or returns a typed technical BLOCK/FAIL when fixed integrity or execution preconditions are not met.
9. Fixed verifier determines mechanical PASS/FAIL/VETO.
10. Append decision and execution records.
11. STOP. No implicit retry and no second cognition cycle.

## 3. Trust model
- LLM output is hostile/untrusted input.
- Exact JSON field set is mandatory; duplicate or unknown fields fail closed.
- Invalid types, lengths, enums, encodings, or parameters fail closed.
- K cannot generate executable/cwd/env/SHA/process-spec fields.
- K is authoritative for the substantive decision. F is authoritative only for deterministic execution validity and fixed technical/integrity preconditions.

## 4. Decision Schema v1
The LLM may return exactly one JSON object with exactly these fields:
```json
{"schema":"K01.DECISION.1","action_id":"A05_NO_ACTION"}
```
Allowed keys: exactly `schema`, `action_id`.
Allowed schema value: exactly `K01.DECISION.1`.
Allowed action IDs: exactly the five registry IDs defined below.
No `params`, command, path, env, process spec, verifier, rationale, retry, timeout, or metadata field is accepted from the LLM.
Any extra field, duplicate key, malformed JSON, trailing object, unknown enum, or oversized response is REJECTED and resolves to a recorded safe failure; it never falls back to a guessed action.

## 5. Initial Action Registry
- `A01_READ_PROJECT_STATE`: return a bounded, schema-checked projection of F authoritative project state.
- `A02_READ_F_STATUS`: return bounded mechanical runtime/acceptance status only.
- `A03_RUN_F_SMOKE_TEST`: trigger one fixed pre-approved F smoke-test action.
- `A04_WRITE_K_DECISION_LOG`: append one fixed-schema, bounded decision marker; no LLM-controlled text payload.
- `A05_NO_ACTION`: execute a registered deterministic no-op and return an explicit no-op receipt.

All five IDs use the same registry lookup, policy decision, receipt, and verifier framework. `A04` and `A05` have no shortcut or green channel.

## 6. Fixed Verifiers
Verifier definitions are registry-owned and immutable for the duration of one execution.
- A01 PASS: response schema valid, source state read succeeded, required bounded fields present.
- A02 PASS: response schema valid and mechanical F status query completed.
- A03 PASS: fixed smoke test exits 0 and its predeclared assertions report zero failures.
- A04 PASS: exactly one valid marker was appended at the expected next log position and durability check succeeds.
- A05 PASS: registry accepted the no-op and emitted a valid no-op receipt; no executable process was started.

K/LLM cannot supply or modify a verifier, expected exit code, path, assertion count, or PASS rule.
Open-world/business judgments are never converted into K01 mechanical PASS.

## 7. F boundary
- K submits only a validated Action ID.
- K cannot submit a process spec, executable path, shell command, argv, cwd, env, hash, user, capability, timeout, or arbitrary payload.
- The standalone boundary adapter performs independent Action Registry lookup and policy/veto semantics for protocol verification only. Real F remains untouched until FK integration.
- A missing/disabled/mismatched registry entry fails closed.
- No F-side change is permitted during K00-K08 standalone build. FK integration will later expose real F actions through its controlled upgrade/acceptance path; K itself can never edit Frozen Authority.
- K01 must not weaken any accepted F01-F20/FP/FS/FH invariant.

## 8. Minimal state files
K01 may read fixed-format constitution/goal/world-state inputs and append bounded JSONL decision/execution records.
No embeddings, automatic summarization, association graph, conflict resolver, self-rewrite, or memory compaction are in scope.
Historical JSONL entries are append-only; K cannot rewrite an earlier decision to make a later outcome look successful.

## 9. K01 PASS gate
K01 is PASS only if all are true:
- strict parser rejects malformed JSON, duplicate keys, extra fields, unknown action IDs, oversize output, and any attempted `params`/command/path/env/process-spec/verifier field;
- every one of A01-A05 traverses the same registry/policy/receipt/verifier framework;
- A05 starts no executable process and returns a verifiable no-op receipt;
- K cannot alter F Frozen Authority or create a free-form process spec;
- each verifier is predeclared and cannot be modified after execution result is known;
- one cycle performs at most one LLM call and one selected action, then logs and stops;
- invalid LLM output produces no selected F action;
- append-only decision/execution logs preserve failed and vetoed attempts;
- mechanical PASS/FAIL/VETO is distinguishable from non-mechanical assessment;
- K00-K08 standalone build does not modify F; real F regression is deferred to FK integration;
- tests include adversarial parser/action attempts and negative authorization cases;
- full K01 targeted/adversarial test suite and Python compile PASS; no real F code/state is modified.

Until every item above has evidence, K01 remains IN_PROGRESS and must not be described as born/complete.
