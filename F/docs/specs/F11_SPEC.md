# KK/F v0.1 Specification — F11 Direct Non-Shell Local Process Executor

Status: PASS

## Scope
F11 executes an already-declared F09 process candidate locally after F10 integrity preflight. It uses direct argv-based process creation, never a command shell, and waits for a bounded result. It has no network/cloud/AI/SSH/Bridge runtime dependency.

## Execution semantics
- timeout_seconds must be a positive int/float; booleans rejected
- F10 preflight must succeed immediately before launch
- argv is `[executable, *declared_argv]`; shell metacharacters remain literal data
- process creation uses `shell=False`, explicit cwd, explicit env, stdin DEVNULL, stdout/stderr pipes, and close_fds
- non-zero process exit is reported verbatim and is not treated as successful health
- timeout kills the launched process, waits for it to terminate, and reports timed_out=true
- successful return includes preflight digest, pid, exit_code, timed_out, stdout, and stderr

## Boundary
F11 does not supervise a long-lived process after the bounded execution call and does not equate exit code 0 with F health or acceptance. TOCTOU between the last preflight and process creation is reduced but not completely eliminated by this Python-level implementation.

## Gate
- isolated executor suite: 14/14 PASS, exit 0
- full F01-F11 regression: 172/172 PASS, exit 0
- Python compile check: exit 0
- static execution-boundary audit: PASS
- shell-metacharacter adversarial test verified no shell interpretation
- timeout test verified bounded kill-and-reap behavior

Evidence: `evidence/f11/`.
F11 = PASS.
