#!/bin/sh
set -eu
RUN=/run/kk-world-observer
VIEW=/run/kk-k-ro
RAW=$RUN/latest.json
mkdir -p "$RUN" "$VIEW"
rm -f "$RAW"
if systemctl is-active --quiet kk-gpt-tool-runtime.service; then
  echo 'approved tool runtime busy; observation skipped fail-closed' >&2
  exit 75
fi
systemd-run --quiet --wait --collect --pipe --unit=kk-gpt-tool-runtime \
  --property=DynamicUser=yes \
  --property=NoNewPrivileges=yes \
  --property=ProtectSystem=strict \
  --property=ProtectHome=tmpfs \
  --property=PrivateTmp=yes \
  --property=RestrictAddressFamilies=AF_UNIX \
  --property=IPAddressDeny=any \
  --property=BindReadOnlyPaths=/root/K/K:$VIEW \
  --setenv=PYTHONPATH=$VIEW/src \
  /usr/bin/python3 -m kk_k.world_observer > "$RAW"
/usr/bin/python3 /root/K/K/tools/world_observation_ingest.py "$RAW"
rm -rf "$VIEW"
