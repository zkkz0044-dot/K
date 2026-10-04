# KK/F Stability Reinforcement — FS02 Exact Release Tree Verification

Status: PASS

## Purpose
FS02 binds an FS01-valid release manifest to actual local bytes in an isolated release root before any future activation. Verification is read-only and fail-closed.

## Invariants
- release root must be an absolute existing real directory, not a symlink
- every declared file is opened without following symlinks
- symlinked ancestors and symlinked files are rejected
- every declared file must be a regular file
- size and SHA-256 must exactly match the FS01 manifest
- undeclared files or symlinks anywhere in the release root are rejected
- directory-only structure is allowed only as needed to contain declared files
- missing files, changed bytes, changed size, file/type substitution, unreadable/corrupt manifest data fail closed
- verification returns the already-verified manifest identity and file count
- no process execution, network access, mutation, deletion, chmod/chown, or activation

## Gate
- isolated adversarial suite PASS
- 20 consecutive isolated repetitions PASS
- full F01-F20 + FP01-FP06 + FS01-FS02 regression PASS
- Python compile PASS
- static external-dependency/mutation audit PASS
- raw evidence retained under `evidence/fs02/`

Gate result: PASS
