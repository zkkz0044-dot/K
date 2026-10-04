## Summary

Describe what changed and why.

## Authority boundary

- [ ] K / F / FK ownership is clear.
- [ ] No execution authority was moved into K model output.
- [ ] No cognitive authority was moved into F.
- [ ] Public schemas are unchanged, or a deliberate new schema version is included.

## Source hygiene

- [ ] No credentials, personal data, runtime state, device identifiers, or private infrastructure details.
- [ ] No local databases, logs, sockets, PID files, caches, or retired provider artifacts.

## Validation

- [ ] `python3 scripts/check_public_tree.py`
- [ ] `./scripts/test_all.sh`
- [ ] Relevant new tests were added or updated.
