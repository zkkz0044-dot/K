# Public release checklist

A public release is allowed only after every required gate below is satisfied.

## Source and privacy

- [ ] No personal memory or conversation history.
- [ ] No runtime audit/evidence history.
- [ ] No credentials, cookies, sessions, or device keys.
- [ ] No private hostnames, account identifiers, repository names, or device bindings.
- [ ] No private networking-client or interface history.
- [ ] No retired provider runtime or model artifacts.
- [ ] No generated databases, sockets, PID files, logs, pytest caches, or Python caches.

## Architecture and tests

- [ ] K tests pass.
- [ ] F tests pass.
- [ ] FK tests pass.
- [ ] Public panel HTTP checks and offline chat restart/recall integration pass.
- [ ] Model candidates and programmatic fallbacks are reported separately; no regression score is presented as general cognition proof.
- [ ] `scripts/check_public_tree.py` passes.
- [ ] `sudo bash scripts/test_clean_install.sh` passes from a disposable staged copy.
- [ ] No test requires retained personal/runtime data from a live K instance.
- [ ] Public schemas and authority boundaries are documented.
- [ ] SHA256 manifest is regenerated after the final change with `python3 scripts/generate_sha256.py`.
- [ ] `python3 scripts/verify_sha256.py` passes against the final tree.

## Publication

- [ ] Open-source license selected.
- [ ] Publisher confirms redistribution rights for source and the three panel icons.
- [ ] SECURITY reporting path configured.
- [ ] Fresh public Git history starts from the sanitized tree.
- [ ] Repository visibility remains private until manual release approval.
- [ ] Final human release gate approved.

No automated process may satisfy the final human release gate.
