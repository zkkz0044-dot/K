#!/bin/sh
set -eu
RUN=/run/kk-world-continuity
RAW=$RUN/latest.json
mkdir -p "$RUN"
rm -f "$RAW"
CTXREC=$(/usr/bin/python3 /root/K/K/tools/continuity_context.py)
CTX=$(printf '%s' "$CTXREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["file"])')
CTXBASE=$(basename "$CTX")
STATE=$(systemctl is-active kk-world-cognition-runtime.service 2>/dev/null || true)
if [ "$STATE" = active ]; then
  echo 'continuity runtime busy' >&2
  exit 75
fi
systemd-run --quiet --wait --collect --pipe --unit=kk-world-cognition-runtime \
  --property=DynamicUser=yes --property=NoNewPrivileges=yes \
  --property=ProtectSystem=strict --property=ProtectHome=tmpfs --property=PrivateTmp=yes \
  --property=RestrictSUIDSGID=yes --property=LockPersonality=yes \
  --property=RestrictAddressFamilies=AF_UNIX --property=IPAddressDeny=any \
  --property=MemoryMax=256M --property=TasksMax=64 --property=UMask=0077 \
  --property=BindReadOnlyPaths=/root/K/K:/run/kk-k-ro \
  --property=BindReadOnlyPaths=/root/K/FK/runtime/model-ipc:/run/kk-model-ipc \
  --setenv=PYTHONPATH=/run/kk-k-ro/src \
  /usr/bin/python3 -m kk_k.world_continuity \
  "/run/kk-k-ro/world/continuity_context/$CTXBASE" > "$RAW"
/usr/bin/python3 /root/K/K/tools/world_continuity_ingest.py "$RAW" "$CTX"
