#!/bin/sh
set -eu
if [ "$#" -lt 2 ]; then
  echo "usage: $0 <evidence-prefix> <command> [args...]" >&2
  exit 64
fi
prefix=$1; shift
mkdir -p "$(dirname "$prefix")"
unit="kk-fh-test-$(date +%s)-$$"
# Tests run outside the development bridge cgroup with a strict independent budget.
# This prevents a hostile/fault-injection test from exhausting the 1 GiB host or
# killing the development control plane that launched it.
set +e
systemd-run --quiet --wait --collect --pipe --service-type=exec \
  --unit="$unit" \
  -p MemoryHigh=192M -p MemoryMax=256M -p TasksMax=128 -p CPUQuota=70% \
  -p RuntimeMaxSec=300 -p KillMode=control-group -p OOMPolicy=stop \
  --working-directory=/root/K/F \
  /bin/sh -c 'exec "$@"' sh "$@" >"$prefix.txt" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" >"$prefix.exit"
exit "$rc"
