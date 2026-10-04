# K00 — Philosophy / Constitution

Status: PASS
Purpose: convert the human-readable K constitution into a strict machine-checkable invariant set that every later K phase must load unchanged.

## Gate
K00 is PASS only if:
- constitution JSON has an exact schema and exact field set; duplicate/unknown fields fail closed;
- K final decision authority is explicit and mandatory; F is a deterministic execution/integrity guard, not an independent decision authority;
- LLM output trust is UNTRUSTED;
- unknown actions/fields are rejected;
- success criteria cannot be weakened after an execution result exists;
- NO_ACTION is legitimate and receives no green channel;
- K has no arbitrary execution authority and cannot rewrite historical records in K01 scope;
- truth seeking outranks preserving prior conclusions;
- model replacement cannot silently replace constitution;
- the only trusted roots are integrity-verified K core and F;
- every model/API/tool/network/web/mail/database/other-agent input defaults to UNTRUSTED_EVIDENCE;
- K trusts its verified identity/core but treats its own judgments as FALLIBLE;
- Soul A/B/C outputs are UNTRUSTED_CANDIDATE until governed and verified;
- standalone K filesystem scope is exactly `/root/K/K`, and every K file API rejects any resolved path outside that root;
- tests, temporary files, acceptance artifacts, and export staging also remain inside `/root/K/K`;
- web-root staging, temporary HTTP transfer, cross-project filesystem access, and external staging are forbidden before explicit FK approval;
- targeted positive/negative tests and Python compile PASS;
- hashes and raw evidence are retained.

K00 contains no autonomous loop, no model call and no F modification.