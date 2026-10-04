# K02 — Durable Structured Memory

Status: PASS
Purpose: give K a minimal durable memory without research-grade automatic memory behavior.

## Scope
- fixed structured current-goal JSON;
- bounded append-only event JSONL with monotonic sequence and hash chaining;
- exact schemas, duplicate/unknown fields fail closed;
- bounded UTF-8 text for non-executable semantic content;
- deterministic load/append/verify primitives.

## Explicit non-goals
No embeddings, vector DB, automatic compression, semantic association graph, automatic conflict resolution, self-rewrite, memory ranking model, or hidden summarization.

## PASS gate
- current goal exact schema validates and can be atomically replaced only through validated API;
- event records exact schema and bounded fields validate;
- event sequence is strictly monotonic from 1;
- each event binds previous event digest; tamper/reorder/delete in the middle is detected;
- append fsyncs the file and parent directory on creation;
- no API rewrites an earlier event;
- malformed/duplicate/extra/oversize/type-confused inputs fail closed;
- targeted/adversarial tests + repeat campaign + Python compile PASS;
- K01 regression remains PASS; real F remains untouched.