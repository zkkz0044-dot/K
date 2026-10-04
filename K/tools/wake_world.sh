#!/bin/sh
set -eu
PIPE=/run/kk-world-daemon/wake.pipe
[ -p "$PIPE" ] || { echo 'WORLD_DAEMON_NOT_READY' >&2; exit 75; }
printf '%s\n' "${1:-event}" > "$PIPE"
