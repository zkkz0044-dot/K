# K External Tool v1 — Exact Three Capabilities

## Frozen scope
Only these external capabilities are enabled in this stage:
1. `files.read`
2. `browser.search`
3. `remote.vps.health`

Everything else remains disabled, including Windows remote, Gmail, GitHub, database and notify.

## Authority boundary
- K core action registry remains exactly A01–A05.
- External capabilities do not become K core actions.
- K runtime has AF_UNIX only and `IPAddressDeny=any`.
- Requests go through the separate F-owned `FK Tool Gateway`.
- ROOT is not accepted as K peer authority.

## Files
- Read-only.
- `/root/K/**` only after realpath resolution.
- Root-owned regular UTF-8 files only.
- Group/world writable files denied.
- Sensitive-name patterns denied.
- Output bounded to 2048 characters.

## Browser/Search
- Search only; no browser click, login, form submit or arbitrary URL execution.
- K and F Tool Gateway remain network-denied.
- Internet access exists only in isolated low-privilege `kk-cap-search.service`.
- Up to 3 bounded results are returned through AF_UNIX.

## Remote
- `remote.vps.health` is read-only host telemetry with no shell and no caller command.
- `remote.windows.health` remains disabled until a dedicated K/F-controlled Windows bridge exists.
- No `remote.exec` exists in this stage.
