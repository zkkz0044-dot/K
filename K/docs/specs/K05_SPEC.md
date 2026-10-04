# K05 — Bounded Planner / Task Graph

Status: PASS
Purpose: turn reasoning output into a finite inspectable plan without granting execution authority.

## Scope
- strict plan JSON with finite task list;
- each task contains bounded purpose text, one pre-approved action_id and dependency IDs;
- max 16 tasks, max dependency depth 8;
- duplicate IDs, missing dependencies, self-dependency and cycles fail closed;
- planner never executes tasks and never carries params/commands/process specs;
- deterministic ready-task calculation.

## PASS gate
- exact plan/task fields; duplicate/extra/trailing/malformed JSON rejected;
- unknown action IDs and free-form execution fields rejected;
- task/plan IDs bounded and validated;
- graph size/depth/cycle/dependency invariants enforced;
- ready tasks depend only on declared completed task IDs;
- targeted/adversarial + repeat + K00-K05 regression + compile PASS;
- real F remains untouched.