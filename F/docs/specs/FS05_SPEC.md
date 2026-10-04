# KK/F Stability Reinforcement — FS05 Atomic Activation and Commit

Status: IN_PROGRESS

## Purpose
Activate an already-staged, FS02-verified candidate by atomically switching a local `current` symlink and then committing FS03 authority state. Ordinary in-process commit failure must restore the previous pointer. Crash interruption between pointer switch and state commit is explicitly deferred to FS06 recovery.

## Invariants
- FS03 state must contain non-null CANDIDATE matching the supplied FS01 manifest identity.
- staged candidate at `<store>/<release_id>` must pass FS02 exactly before any pointer mutation.
- existing `current` must be an exact one-component relative symlink naming current ACTIVE release_id; ambiguity/symlink substitution/absolute target fails closed.
- candidate cannot already be ACTIVE.
- current pointer switch uses a same-directory temporary symlink + atomic `os.replace` + parent fsync.
- state commit is generation-monotonic: new ACTIVE=old CANDIDATE, new LKG=old ACTIVE, new CANDIDATE=null.
- if state commit raises after pointer switch, pointer is synchronously restored to old ACTIVE and fsynced; if restoration fails, activation fails loudly for FS06 reconciliation.
- no release bytes are modified or deleted by activation.
- no network/cloud/AI/SSH/Bridge runtime dependency.
