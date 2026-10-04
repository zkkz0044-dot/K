# FKP06 — External Tool Layer v1

## Accepted architecture

`GPT/K runtime -> K Tool Layer -> K verifier -> FK Tool Gateway -> F-owned adapter/capability`

The legacy FKP05 action gateway `@kk-fk-v1` and its exact five-action surface remain unchanged. External tools use separate abstract AF_UNIX `@kk-fk-tool-v1`.

## Accepted client identities

- `kk-k-runtime.service` — transient DynamicUser K runtime.
- `kk-gpt-tool-runtime.service` — transient DynamicUser GPT tool runtime used before K takes over.
- UID 0/root direct callers are denied.

## Enabled L0 tools

- `remote.vps.health` — fixed no-argument host health; no shell/network.
- `files.read` — bounded UTF-8 read restricted to `/root/K/K/`; F/FK, runtime/state/models/vendor and sensitive-name paths denied.
- `browser.search` — bounded query via isolated network worker; worker accepts only the F Tool Gateway cgroup.

## Security invariants

- Exact request schemas; unknown tools and extra fields fail closed.
- Each enabled tool requires a hard-coded K verifier contract.
- K/GPT have no direct network access in their tool runtimes.
- Network worker cannot be called directly by K/GPT/root; only F Tool Gateway may call it.
- F remains final execution/policy authority.
