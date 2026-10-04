# FKP03 — Human Interface + Live Cognition + Identity/Conversation Continuity

Status: INTERNAL_PASS_AWAITING_USER_DIALOGUE

## PASS gate
1. Human input enters only through a local SSH/TTY console; no public HTTP, webhook, SHOP, Nginx or third-project path.
2. Plain natural language defaults to cognitive CHAT. ASK/PLAN/REMEMBER are explicit cognitive modes; no human-chat field can directly carry Action ID, ProcessSpec, path, argv, env or verifier.
3. APPROVE/EXECUTE/RUN are not implemented in FKP03; privileged execution remains blocked.
4. K runtime remains systemd DynamicUser in exact kk-k-runtime.service cgroup, with /root still 0700 and only verified read-only K mirror.
5. K identity is root-owned, exact-schema, integrity-guarded and explicitly independent of the model provider.
6. Conversation history is F-owned canonical K02 events; K cannot rewrite or delete prior human/K messages.
7. Every visible user message is durably recorded before cognition; every visible K reply is durably recorded before display.
8. Dialogue uses three sequential fallible roles A→B→C for open questions; stable self-identity facts may be answered mechanically by K. Model text is UNTRUSTED_CANDIDATE and K owns all structure; no execution authority exists in the dialogue path.
9. A real model provider is used for internal acceptance; mock/injected providers cannot satisfy the live-provider gate.
10. The model runtime is isolated, offline, non-root, read-only, cannot see F or K authority/state, and is replaceable without changing K identity.
11. Root/development-bridge direct access to model/audit runtime is rejected where peer authentication applies.
12. Model/provider failure, malformed protocol/output, oversized output or witness failure stops the turn; no silent fallback to mock or automatic action.
13. K/F/FK regressions, compile, fresh FP06 and repeated real DynamicUser dialogue tests remain PASS.
14. FKP03E is not PASS until the user personally talks to the real server K and accepts the result.
