# KK/F Adversarial Hardening — FH02 Critical Path Resolution

Status: PASS

## Purpose
Reject parent-directory symlink traversal and path-component substitution for critical immutable startup inputs and launch objects.

## Scope
- executable path used by FH01 launch guard
- cwd path used by FH01 launch guard
- Frozen Authority manifest path
- production runtime configuration path

Mutable state/store namespace ownership and immutability are handled separately in FH04; anti-rollback semantics are FH03.

## Security invariants
- absolute paths are canonical, normalized, NUL-free; dot/double-slash/trailing-slash ambiguity rejected.
- every parent component is opened from `/` with directory fd + `O_NOFOLLOW`.
- final file/directory component is also opened with `O_NOFOLLOW`.
- authority/config bytes are read from the already-opened fd; pathname replacement after open cannot substitute bytes.
- launch_guard executable/cwd now use the same no-symlink component walk before FH01 fd-bound execution.
- critical file reads have explicit maximum sizes.

## PASS gate
- isolated FH02 adversarial suite: 9/9 PASS, exit 0.
- parent-symlink rejection and authority/config post-open path-swap tests PASS.
- 300 repeated rejection iterations: no fd growth beyond +1.
- first targeted/full regression failures retained: FP06 cold-start harness exposed startup-grace self-DoS under loaded VPS.
- first fresh production fault-injection failure retained: fixed 0.4s backoff / 0.5s startup windows were too tight under scheduler contention.
- corrected full regression: 418/418 PASS, exit 0.
- Python compile: exit 0.
- corrected fresh production fault injection: PASS, exit 0; cold start, non-root systemd, lock denial, bounded restart/backoff/HOLD_FAILED, supervisor restart persistence and isolated network namespace all PASS.

## Evidence
`evidence/fh02/`

## Residual risk
- mutable runtime state, lock, release-store ownership/mode invariants are deferred to FH04.
- anti-rollback/replay semantics are FH03.
