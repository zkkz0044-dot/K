#!/bin/bash
set -euo pipefail
RUN=/run/kk-world-cognition
INITIAL=$RUN/initial-think.json
# Keep the lock through all think, follow-up and retention staging phases.
# A rejected invocation must not remove another round's working files.
exec 9>"$RUN.lock"
if ! flock -n 9; then
  echo 'world cognition cycle busy; skipped fail-closed' >&2; exit 75
fi
if systemctl is-active --quiet kk-world-cognition-runtime.service ||
   systemctl is-active --quiet kk-gpt-tool-runtime.service; then
  echo 'world cognition or tool runtime busy; skipped fail-closed' >&2; exit 75
fi
mkdir -p "$RUN"
rm -f "$RUN"/*.json
EVID=${1:-$(ls -1t /root/K/K/world/evidence/*.json 2>/dev/null | sed -n '1p')}
SOURCE_EVID=${2:-$EVID}
SOURCE_RAW=${3:-}
MAX_DEPTH=${KK_WORLD_MAX_FOLLOWUP_DEPTH:-3}
case "$MAX_DEPTH" in 0|1|2|3) ;; *) echo 'invalid followup depth' >&2; exit 64;; esac
[ -n "$EVID" ] || { echo 'no world evidence' >&2; exit 66; }
case "$EVID" in /root/K/K/*) ;; *) echo 'evidence path outside K' >&2; exit 64;; esac
RO_EVID=/run/kk-k-ro/${EVID#/root/K/K/}
run_think(){
  local src=$1 out=$2
  systemd-run --quiet --wait --collect --pipe --unit=kk-world-cognition-runtime \
    --property=DynamicUser=yes --property=NoNewPrivileges=yes \
    --property=ProtectSystem=strict --property=ProtectHome=tmpfs --property=PrivateTmp=yes \
    --property=RestrictSUIDSGID=yes --property=LockPersonality=yes \
    --property=RestrictAddressFamilies=AF_UNIX --property=IPAddressDeny=any \
    --property=MemoryMax=256M --property=TasksMax=64 --property=UMask=0077 \
    --property=BindReadOnlyPaths=/root/K/K:/run/kk-k-ro \
    --property=BindReadOnlyPaths=/root/K/FK/runtime/model-ipc:/run/kk-model-ipc \
    --setenv=PYTHONPATH=/run/kk-k-ro/src \
    /usr/bin/python3 -m kk_k.world_think "$src" > "$out"
}
run_think "$RO_EVID" "$INITIAL"
CURRENT_EVID=$EVID
CURRENT_THINK=$INITIAL
EPHEMERAL_ARGS=()
[ -z "$SOURCE_RAW" ] || EPHEMERAL_ARGS+=(--ephemeral "$SOURCE_RAW")
depth=1
while [ "$depth" -le "$MAX_DEPTH" ]; do
  QCOUNT=$(/usr/bin/python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d["thought"]["follow_up_queries"]))' "$CURRENT_THINK")
  [ "$QCOUNT" -gt 0 ] || break
  if systemctl is-active --quiet kk-gpt-tool-runtime.service; then
    echo 'tool runtime busy; follow-up skipped fail-closed' >&2; exit 75
  fi
  FRAW=$RUN/followup-$depth.json
  systemd-run --quiet --wait --collect --pipe --unit=kk-gpt-tool-runtime \
    --property=DynamicUser=yes --property=NoNewPrivileges=yes \
    --property=ProtectSystem=strict --property=ProtectHome=tmpfs --property=PrivateTmp=yes \
    --property=RestrictAddressFamilies=AF_UNIX --property=IPAddressDeny=any \
    --property=BindReadOnlyPaths=/root/K/K:/run/kk-k-ro \
    --setenv=PYTHONPATH=/run/kk-k-ro/src \
    /usr/bin/python3 -m kk_k.world_followup_from_think "$CURRENT_THINK" > "$FRAW"
  FREC=$(/usr/bin/python3 /root/K/K/tools/world_followup_ingest.py "$FRAW")
  FCOUNT=$(printf '%s' "$FREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence_items"])')
  FFILE=$(printf '%s' "$FREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["file"])')
  FEVID=$(printf '%s' "$FREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence_file"])')
  EPHEMERAL_ARGS+=(--ephemeral "$FFILE" --ephemeral "$FEVID")
  [ "$FCOUNT" -gt 0 ] || break
  MERGED=$RUN/merged-$depth.json
  /usr/bin/python3 /root/K/K/tools/world_context_merge.py "$CURRENT_EVID" "$FEVID" "$MERGED"
  AREC=$(/usr/bin/python3 /root/K/K/tools/world_context_archive.py "$MERGED")
  CURRENT_EVID=$(printf '%s' "$AREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["file"])')
  EPHEMERAL_ARGS+=(--ephemeral "$CURRENT_EVID")
  THINK=$RUN/think-$depth.json
  RO_PATH=/run/kk-k-ro/${CURRENT_EVID#/root/K/K/}
  run_think "$RO_PATH" "$THINK"
  CURRENT_THINK=$THINK
  depth=$((depth + 1))
done
/usr/bin/python3 /root/K/K/tools/world_retention_stage.py \
  "$EVID" "$INITIAL" "$CURRENT_EVID" "$CURRENT_THINK" \
  --source-path "$SOURCE_EVID" "${EPHEMERAL_ARGS[@]}"
