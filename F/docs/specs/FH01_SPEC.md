# KK/F Adversarial Hardening — FH01 Executable Identity / Launch TOCTOU Elimination

Status: PASS

## Purpose
Bind integrity verification to the exact opened executable inode and cwd directory object used by process launch so path replacement after verification cannot substitute different bytes or a different working directory.

## Security invariants
- launch spec remains strict F09 input.
- executable is opened with O_NOFOLLOW and verified by fd, not by a path reopened later.
- executable must be regular, executable, non-group/world-writable, and have exactly one hard link.
- device/inode/mode/link-count/size/mtime/ctime must remain stable across hashing.
- child exec path is /proc/self/fd/<verified-fd> with pass_fds; cwd likewise binds to the verified opened directory fd.
- symlink/FIFO/hardlink/group-writable candidates fail closed.
- path replacement after verification cannot change the executable or cwd object actually used by the child.

## PASS gate
- isolated adversarial suite: 10/10 PASS.
- targeted legacy launch/supervision regression: 102/102 PASS.
- executable-path + cwd-path swap races repeated 50 rounds / 100 race cases: PASS.
- full regression: 409/409 PASS, exit 0.
- Python compile: exit 0.
- fresh FP06 production fault injection: PASS, exit 0 including network namespace.

## Evidence
`evidence/fh01/`

Residual risk intentionally deferred: inherited verified launch descriptors and broader privilege/resource containment are handled in FH05; parent-directory path traversal/authority hardening is handled in FH02.
