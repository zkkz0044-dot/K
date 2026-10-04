# KK/F v0.1 Specification — F13 Managed Long-Running Local Process Primitive

Status: PASS

## Scope
F13 introduces a managed local long-running process handle built only on the already-accepted F09 launch contract, F10 integrity preflight, and F12 execution-status classifier. It launches directly without a shell, exposes process identity and observation, and supports bounded graceful stop with forced kill fallback. It does not infer HEALTHY from process existence and does not implement restart policy, supervision, authority, cloud control, or external-service dependencies.

## Semantics
- F10 preflight must verify the candidate immediately before launch
- launch uses direct argv process creation with `shell=False`
- explicit cwd and explicit environment are used
- stdin is disabled; stdout/stderr are not a correctness dependency of this primitive
- returned handle exposes a positive integer pid and the verified executable SHA-256
- observation maps live child => `RUNNING`, clean exit 0 => `STOPPED`, non-zero/signal exit => `FAILED` through F12
- process existence never yields `HEALTHY`
- `grace_seconds` must be a positive number; bool/zero/negative reject fail-closed
- stop first requests graceful termination, then force-kills and reaps after the bounded grace interval
- stopping an already-cleanly-exited child is deterministic and idempotently `STOPPED`
- candidate hash changes between declaration and launch block launch through F10
- shell metacharacters remain literal argv data
- no GitHub/cloud drive/ChatGPT/Codex/Supabase/SSH/Bridge runtime dependency

## Gate
- prior real failures retained in `evidence/f13/`
- corrected isolated suite: 12/12 PASS, exit 0
- stability repetition: 20 consecutive isolated runs PASS, exit 0
- full F01-F13 regression: 194/194 PASS, exit 0
- Python compile check: exit 0
- static dependency/execution-boundary audit: PASS, exit 0

Evidence: `evidence/f13/`.
F13 = PASS.
