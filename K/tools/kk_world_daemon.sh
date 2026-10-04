#!/bin/bash
set -u
STATE=/run/kk-world-daemon
PIPE=$STATE/wake.pipe
MIN_YIELD=300
MAX_YIELD=1800
DELAY=$MIN_YIELD
mkdir -p "$STATE" /root/K/K/world/sensory_inbox /root/K/K/world/sensory_receipts
rm -f "$PIPE"
mkfifo -m 600 "$PIPE"
exec 3<>"$PIPE"
trap 'rm -f "$PIPE"; exit 0' INT TERM EXIT
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$1"; }
refresh_current_model(){
  if /usr/bin/python3 /root/K/K/tools/world_current_model.py >/dev/null; then
    log 'CURRENT_MODEL_REFRESH=PASS'; return 0
  fi
  log 'CURRENT_MODEL_REFRESH=FAIL'; return 1
}
latest_evidence(){ ls -1t /root/K/K/world/evidence/*.json 2>/dev/null | sed -n '1p'; }
LAST_DELIVERED=0
scan_world(){
  local evid base delivery receipt rec delivered duplicates
  LAST_DELIVERED=0
  log 'SELF_OBSERVE_START'
  if ! systemctl start kk-world-observation-cycle.service; then
    log 'OBSERVATION_FAIL'; return 1
  fi
  evid=$(latest_evidence || true)
  [ -n "$evid" ] || { log 'NO_EVIDENCE'; return 1; }
  base=$(basename "$evid")
  delivery=/root/K/K/world/sensory_inbox/$base
  receipt=/root/K/K/world/sensory_receipts/$base
  rec=$(/usr/bin/python3 /root/K/FK/tools/world_exact_dedup.py prepare "$evid" "$delivery" "$receipt") || { log 'DEDUP_FAIL'; return 1; }
  delivered=$(printf '%s' "$rec" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["delivered_items"])')
  duplicates=$(printf '%s' "$rec" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["exact_duplicates"])')
  log "SENSORY source=$(printf '%s' "$rec" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["source_items"])') delivered=$delivered exact_duplicates=$duplicates"
  if [ "$delivered" -eq 0 ]; then
    if /usr/bin/python3 /root/K/K/tools/world_retention_finalize.py duplicate "$evid" "$delivery" "$receipt" >/dev/null; then
      refresh_current_model || return 1
      log 'EXACT_DUPLICATES_ONLY_CLEANED'
      local curiosity_rec curiosity_status
      if curiosity_rec=$(/root/K/K/tools/run_world_curiosity_cycle.sh); then
        curiosity_status=$(printf '%s' "$curiosity_rec" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","UNKNOWN"))')
        log "CURIOSITY status=$curiosity_status"
      else
        log 'CURIOSITY_FAIL'
      fi
      return 0
    fi
    log 'DUPLICATE_RETENTION_CLEANUP_FAIL'
    return 1
  fi
  if ! /root/K/K/tools/run_world_cognition_cycle.sh "$delivery" "$evid"; then
    log 'COGNITION_FAIL_UNCOMMITTED'; return 1
  fi
  if ! /usr/bin/python3 /root/K/FK/tools/world_exact_dedup.py commit "$delivery" >/dev/null; then
    log 'SEEN_COMMIT_FAIL'; return 1
  fi
  if ! /usr/bin/python3 /root/K/K/tools/world_retention_finalize.py cognized "$evid" "$delivery" "$receipt" >/dev/null; then
    log 'RETENTION_FINALIZE_FAIL'; return 1
  fi
  refresh_current_model || return 1
  LAST_DELIVERED=$delivered
  log "K_SAW delivered=$delivered"
  return 0
}

log 'WORLD_DAEMON_ACTIVE_START'
scan_world || true
while true; do
  if IFS= read -r -t "$DELAY" event <&3; then
    log "WAKE ${event:-event}"
  else
    log 'SELF_OBSERVE'
  fi
  if scan_world; then
    if [ "$LAST_DELIVERED" -gt 0 ]; then
      DELAY=$MIN_YIELD
    else
      DELAY=$((DELAY * 2))
      [ "$DELAY" -le "$MAX_YIELD" ] || DELAY=$MAX_YIELD
    fi
  else
    DELAY=$((DELAY * 2))
    [ "$DELAY" -le "$MAX_YIELD" ] || DELAY=$MAX_YIELD
  fi
  log "RESOURCE_YIELD seconds=$DELAY"
done
