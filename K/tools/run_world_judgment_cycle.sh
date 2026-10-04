#!/bin/sh
set -eu
RUN=/run/kk-world-judge
VIEW=/run/kk-world-k-ro
RAW=$RUN/latest.json
EVIDENCE_DIR=/root/K/K/world/evidence
mkdir -p "$RUN" "$VIEW"
rm -f "$RAW"
if systemctl is-active --quiet kk-world-cognition-runtime.service; then
  echo 'world cognition runtime busy; judgment skipped fail-closed' >&2
  exit 75
fi
LATEST=$(find "$EVIDENCE_DIR" -maxdepth 1 -type f -name '*.json' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
if [ -z "$LATEST" ] || [ ! -f "$LATEST" ]; then
  echo 'no world evidence available' >&2
  exit 66
fi
BASE=$(basename "$LATEST")
systemd-run --quiet --wait --collect --pipe --unit=kk-world-cognition-runtime.service \
  --property=DynamicUser=yes \
  --property=NoNewPrivileges=yes \
  --property=ProtectSystem=strict \
  --property=ProtectHome=tmpfs \
  --property=PrivateTmp=yes \
  --property=RestrictSUIDSGID=yes \
  --property=LockPersonality=yes \
  --property=RestrictAddressFamilies=AF_UNIX \
  --property=IPAddressDeny=any \
  --property=MemoryMax=256M \
  --property=TasksMax=64 \
  --property=UMask=0077 \
  --property=BindReadOnlyPaths=/root/K/K:$VIEW \
  --property=BindReadOnlyPaths=/root/K/FK/runtime/model-ipc:/run/kk-model-ipc \
  --setenv=PYTHONPATH=$VIEW/src \
  /usr/bin/python3 -m kk_k.world_judge "$VIEW/world/evidence/$BASE" > "$RAW"
/usr/bin/python3 /root/K/K/tools/world_judgment_ingest.py "$RAW"
rm -rf "$VIEW"
