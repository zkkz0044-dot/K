# K07 — Critic / Evidence / Mechanical Verdict

Status: PASS
Purpose: prevent K from grading its own open-world judgment as mechanical success.

## Scope
- fixed verifier comes only from K01 Action Registry;
- evidence receipt is canonically hashed and bounded;
- mechanical verdict is PASS / FAIL / VETO / REJECTED;
- bounded assessment text is stored separately and cannot alter verdict;
- criteria_id is registry-derived; caller/model cannot supply or modify it.

## PASS gate
- PASS/FAIL/VETO produced only by predeclared verifier;
- malformed/extra/mismatched receipt becomes REJECTED or controlled failure, never PASS;
- assessment saying PASS cannot turn mechanical FAIL into PASS;
- assessment saying FAIL cannot change a valid mechanical PASS;
- evidence digest changes when receipt changes;
- no API accepts caller-supplied verifier/criteria/expected exit code;
- targeted/adversarial + repeat + K00-K07 regression + compile PASS;
- real F remains untouched.