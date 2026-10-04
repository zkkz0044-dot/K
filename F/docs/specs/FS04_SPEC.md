# KK/F Stability Reinforcement — FS04 Isolated Candidate Staging Transaction

Status: IN_PROGRESS

## Purpose
Copy an FS01/FS02-verified candidate release into an isolated local release store without changing ACTIVE/CANDIDATE/LKG authority state. A staged release becomes visible at its final release-id path only after its copied bytes re-verify exactly.

## Invariants
- Source manifest must validate under FS01 and source tree must pass FS02 before staging.
- release store root must be absolute, existing, real directory, not symlink.
- final directory name is exactly release_id; preexisting final path fails closed and is never overwritten.
- staging uses a newly-created private same-parent temporary directory.
- only declared files are copied; file data is fsynced.
- completed temp tree must independently pass FS02 against the manifest before publication.
- publication is one same-filesystem rename from verified temp directory to final release-id directory, followed by parent-directory fsync.
- any pre-publication failure removes the private temp tree and leaves no final release visible.
- FS04 never mutates release-role state, never activates or executes a release.
- no network/cloud/AI/SSH/Bridge runtime dependency.

## Gate
Adversarial isolated tests, repeated runs, full regression, compile/static audit; raw failures retained.
