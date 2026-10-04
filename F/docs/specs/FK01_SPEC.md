# FK01 — Authenticated Minimal K→F Gateway

Status: READY_AFTER_K_SOUL_ACCEPTANCE
Purpose: prove one real K→F IPC path without granting K filesystem access to F or weakening accepted F.

## Transport
- Linux abstract AF_UNIX socket only; no pathname socket or shared directory.
- No TCP, HTTP, cloud, web root, Nginx, SHOP, or external staging.
- K never reads/writes `/root/K/F`; F never reads/writes `/root/K/K`.
- Request schema is exactly `schema` + `action_id`; no params or free-form payload.
- Production peer UID is verified with `SO_PEERCRED`; cgroup identity is verified when deployed.
- Unknown peer, malformed request, duplicate/extra field, oversize, trailing JSON, or unknown action fails closed.

## Initial enablement
- Stage 1 real transport permits only `A05_NO_ACTION`.
- A01/A02 remain disabled until FK01 A05-only acceptance passes.
- A04 remains disabled until read-only FK02 passes.
- A03 remains disabled until explicit human-approved FK04.
- Static registry may know A01-A05, but disabled actions must return VETO and create no side effect.

## Authority
- F performs independent registry/policy lookup and emits the receipt.
- F final VETO is absolute.
- K/LLM/Soul A/B/C cannot create shell, argv, path, env, process spec, verifier, timeout, or new action.
- Existing Frozen Authority v0.2 is not modified or bypassed.

## PASS gate
FK01 is PASS only if:
- KS01–KS03 three-soul layer is already PASS and does not gain direct execution authority;
- abstract AF_UNIX transport works without shared filesystem staging;
- non-K peer identity is denied before action execution;
- A05 traverses the real registry/policy/receipt/verifier path and starts no process;
- A01-A04 are VETOED during FK01 and produce no unintended side effects;
- malformed/oversize/injected/replayed requests fail closed;
- gateway restart/crash cannot broaden permissions or lose the disabled-action policy;
- K full regression remains PASS;
- F full regression and final acceptance remain PASS;
- fresh FP06 fault injection remains PASS;
- evidence and hashes are retained inside `/root/K/F` or `/root/K/K` only.

Until all evidence exists, FK01 must not be described as merged or production-ready.

## Seam-risk release blockers (2026-09-05)
- FK01 acceptance cannot inherit trust from standalone K mocks. Real K request bytes must traverse the real F-owned gateway and return a real F-generated typed receipt.
- The action mapping layer is itself authority-bearing code. It must be static/F-owned/fail-closed and cannot dynamically construct ProcessSpec data from K input.
- Any process-launching FK action must still traverse the relevant F authority + launch/preflight/execution controls; adapter success alone is never PASS evidence.
- VETO receipts must retain a bounded stable F-owned reason_code plus validation stage. Raw exception strings are not protocol reason codes and must not be used as authority.
- Current FK scope contains no long-lived supervised-process control action. Such actions are forbidden until a dedicated runtime_cycle/health-supervisor state-transition contract exists.
- FK01 cannot be marked PASS until R1/R2/R4 in FK_SEAM_RISK_REGISTER.md have direct adversarial integration evidence.
